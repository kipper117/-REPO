"""
모든 데이터 소스를 모아 snapshot.json으로 저장하고,
결측/이상치를 검사한다. 문구 생성(formatters)은 이 snapshot만 보고 동작해야 한다
(각 formatter가 직접 yfinance/FRED를 다시 호출하지 않는다 -> 값 불일치 방지).
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone

from . import config
from .data_sources import fred_client, finnhub_client, yfinance_client

logger = logging.getLogger(__name__)

# 대표 거래일(헤더 날짜 + 기대 거래일 검증)은 이 세 지수만으로 판단한다.
# DXY(거의 24시간 거래)나 FRED(발표 시각이 달라 당일 데이터가 늦게 올라올 수 있음)는
# 발행/거래 시간이 달라서 날짜가 어긋나기 쉬우므로 대표 거래일 판정에서 제외한다.
PRIMARY_TRADE_DATE_SOURCES = ("S&P500", "NASDAQ", "DOW")


def _check_stock_anomaly(change_pct: float) -> bool:
    return abs(change_pct) > config.STOCK_ANOMALY_PCT


def _check_rate_anomaly(change_bp: float) -> bool:
    return abs(change_bp) > config.RATE_ANOMALY_BP


def build_snapshot() -> dict:
    """모든 소스를 조회해 snapshot dict를 만든다. (네트워크 호출 발생)"""
    failures: list[dict] = []
    anomalies: list[dict] = []
    trade_dates_seen: list[str] = []  # 디버그/참고용 (중복 허용)
    primary_trade_dates: list[str] = []  # 대표 거래일 판정용 (3대 지수만)

    # --- 지수/달러인덱스 ---
    indices: dict[str, dict] = {}
    for name, ticker in config.INDEX_TICKERS.items():
        result = yfinance_client.fetch_last_two_closes(ticker)
        indices[name] = result
        if result.get("ok"):
            trade_dates_seen.append(result["trade_date"])
            if name in PRIMARY_TRADE_DATE_SOURCES:
                primary_trade_dates.append(result["trade_date"])
            if _check_stock_anomaly(result["change_pct"]):
                anomalies.append({"item": name, "value": result["change_pct"], "kind": "stock_pct"})
        else:
            failures.append({"item": name, "reason": result.get("reason")})

    # --- 기타 환율 (원/달러 등) ---
    fx: dict[str, dict] = {}
    for name, ticker in config.FX_TICKERS.items():
        result = yfinance_client.fetch_last_two_closes(ticker)
        fx[name] = result
        if result.get("ok"):
            trade_dates_seen.append(result["trade_date"])
            if _check_stock_anomaly(result["change_pct"]):
                anomalies.append({"item": name, "value": result["change_pct"], "kind": "stock_pct"})
        else:
            failures.append({"item": name, "reason": result.get("reason")})

    # --- 해외 지수 (거래소 휴장일이 제각각이라 대표 거래일 판정에서 제외) ---
    global_indices: dict[str, dict] = {}
    for name, ticker in config.GLOBAL_INDEX_TICKERS.items():
        result = yfinance_client.fetch_last_two_closes(ticker)
        global_indices[name] = result
        if result.get("ok"):
            trade_dates_seen.append(result["trade_date"])
            if _check_stock_anomaly(result["change_pct"]):
                anomalies.append({"item": name, "value": result["change_pct"], "kind": "stock_pct"})
        else:
            failures.append({"item": name, "reason": result.get("reason")})

    # --- 원자재 (WTI 등) ---
    commodities: dict[str, dict] = {}
    for name, ticker in config.COMMODITY_TICKERS.items():
        result = yfinance_client.fetch_last_two_closes(ticker)
        commodities[name] = result
        if result.get("ok"):
            trade_dates_seen.append(result["trade_date"])
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
            trade_dates_seen.append(result["trade_date"])
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
            trade_dates_seen.append(result["trade_date"])
            if _check_rate_anomaly(result["change_bp"]):
                anomalies.append({"item": name, "value": result["change_bp"], "kind": "rate_bp"})
        else:
            failures.append({"item": name, "reason": result.get("reason")})

    # --- 뉴스 (Claude 코멘트 참고용, 문자 본문엔 직접 안 들어감) ---
    news = finnhub_client.fetch_market_headlines()
    if not news.get("ok"):
        failures.append({"item": "news_headlines", "reason": news.get("reason")})

    # 대표 거래일: S&P500/NASDAQ/DOW 중 가장 많이 나온 날짜(보통 셋 다 동일).
    # DXY/종목/금리는 거래·발표 시간이 달라 날짜가 어긋날 수 있어 판정에서 제외한다.
    trade_date = Counter(primary_trade_dates).most_common(1)[0][0] if primary_trade_dates else None

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trade_date": trade_date,
        "trade_dates_seen": sorted(set(trade_dates_seen)),
        "indices": indices,
        "fx": fx,
        "global_indices": global_indices,
        "commodities": commodities,
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
