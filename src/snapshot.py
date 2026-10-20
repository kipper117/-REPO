"""
모든 데이터 소스를 모아 snapshot.json으로 저장하고,
결측/이상치를 검사한다. 문구 생성(formatters)은 이 snapshot만 보고 동작해야 한다
(각 formatter가 직접 yfinance/FRED를 다시 호출하지 않는다 -> 값 불일치 방지).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from . import config
from .data_sources import fred_client, finnhub_client, yfinance_client

logger = logging.getLogger(__name__)


def _check_stock_anomaly(change_pct: float) -> bool:
    return abs(change_pct) > config.STOCK_ANOMALY_PCT


def _check_rate_anomaly(change_bp: float) -> bool:
    return abs(change_bp) > config.RATE_ANOMALY_BP


def build_snapshot() -> dict:
    """모든 소스를 조회해 snapshot dict를 만든다. (네트워크 호출 발생)"""
    failures: list[dict] = []
    anomalies: list[dict] = []
    trade_dates: set[str] = set()

    # --- 지수/달러인덱스 ---
    indices: dict[str, dict] = {}
    for name, ticker in config.INDEX_TICKERS.items():
        result = yfinance_client.fetch_last_two_closes(ticker)
        indices[name] = result
        if result.get("ok"):
            trade_dates.add(result["trade_date"])
            if _check_stock_anomaly(result["change_pct"]):
                anomalies.append({"item": name, "value": result["change_pct"], "kind": "stock_pct"})
        else:
            failures.append({"item": name, "reason": result.get("reason")})

    # --- 시가총액 상위 20개 종목 ---
    top20: list[dict] = []
    for stock in config.TOP20_STOCKS:
        ticker = stock["ticker"]
        result = yfinance_client.fetch_last_two_closes(ticker)
        entry = {"ticker": ticker, "name_kr": stock["name_kr"], "sector": stock["sector"], **result}
        top20.append(entry)
        if result.get("ok"):
            trade_dates.add(result["trade_date"])
            if _check_stock_anomaly(result["change_pct"]):
                anomalies.append({"item": ticker, "value": result["change_pct"], "kind": "stock_pct"})
        else:
            failures.append({"item": ticker, "reason": result.get("reason")})

    # --- 금리 (FRED, 단일 소스) ---
    rates: dict[str, dict] = {}
    for name, series_id in config.FRED_SERIES.items():
        result = fred_client.fetch_latest_two_observations(series_id)
        rates[name] = result
        if result.get("ok"):
            trade_dates.add(result["trade_date"])
            if _check_rate_anomaly(result["change_bp"]):
                anomalies.append({"item": name, "value": result["change_bp"], "kind": "rate_bp"})
        else:
            failures.append({"item": name, "reason": result.get("reason")})

    # --- 뉴스 (Claude 코멘트 참고용, 문자 본문엔 직접 안 들어감) ---
    news = finnhub_client.fetch_market_headlines()
    if not news.get("ok"):
        failures.append({"item": "news_headlines", "reason": news.get("reason")})

    # 가장 흔한(=다수가 동의하는) 거래일을 대표 거래일로 채택
    trade_date = max(trade_dates, key=lambda d: sum(1 for t in trade_dates if t == d)) if trade_dates else None

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trade_date": trade_date,
        "trade_dates_seen": sorted(trade_dates),
        "indices": indices,
        "top20_stocks": top20,
        "rates": rates,
        "news": news,
        "failures": failures,
        "anomalies": anomalies,
    }
    return snapshot


def save_snapshot(snapshot: dict, path: str = config.SNAPSHOT_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    logger.info("snapshot saved to %s", path)
