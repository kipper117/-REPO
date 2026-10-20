"""
yfinance를 통해 지수/종목 시세를 가져온다.
각 항목은 (성공, 값 dict) 또는 (실패, 사유)로 반환하며 예외를 호출부로 올리지 않는다.
-> snapshot.py가 실패 항목을 모아 "섹션 생략 + 경고"로 처리할 수 있도록 하기 위함.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_last_two_closes(ticker: str) -> dict:
    """
    최근 2거래일 종가를 가져와 등락률을 계산한다.
    성공 시: {"ok": True, "value": 마지막종가, "prev_value": 전일종가,
              "change_pct": 등락률(%), "trade_date": "YYYY-MM-DD"}
    실패 시: {"ok": False, "reason": "..."}
    """
    try:
        hist = yf.Ticker(ticker).history(period="5d", interval="1d")
        hist = hist.dropna(subset=["Close"])
        if len(hist) < 2:
            return {"ok": False, "reason": f"insufficient history ({len(hist)} rows)"}

        last_row = hist.iloc[-1]
        prev_row = hist.iloc[-2]
        last_close = float(last_row["Close"])
        prev_close = float(prev_row["Close"])
        if prev_close == 0:
            return {"ok": False, "reason": "prev_close is zero"}

        change_pct = (last_close - prev_close) / prev_close * 100.0
        trade_date = hist.index[-1].strftime("%Y-%m-%d")

        return {
            "ok": True,
            "value": last_close,
            "prev_value": prev_close,
            "change_pct": change_pct,
            "trade_date": trade_date,
        }
    except Exception as exc:  # noqa: BLE001 - 데이터 소스 실패는 전부 포착해서 섹션 생략 처리
        logger.warning("yfinance fetch failed for %s: %s", ticker, exc)
        return {"ok": False, "reason": str(exc)}


def fetch_many(tickers: list[str]) -> dict[str, dict]:
    """여러 티커를 한 번에 조회. {ticker: fetch_last_two_closes 결과}"""
    return {ticker: fetch_last_two_closes(ticker) for ticker in tickers}
