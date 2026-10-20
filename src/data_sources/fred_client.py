"""
FRED API로 금리 시계열을 가져온다.
주식 문자/채권 문자가 서로 다른 값을 쓰는 문제를 막기 위해,
금리는 반드시 이 모듈을 통해서만 가져오도록 한다 (다른 곳에서 yfinance로 금리 가져오지 말 것).
"""
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_latest_two_observations(series_id: str) -> dict:
    """
    FRED 시리즈의 최근 2개 유효 관측치를 가져와 bp 변동을 계산한다.
    FRED 금리 값은 % 단위(예: 5.09)로 오므로, bp 변동 = (최근 - 직전) * 100.

    성공 시: {"ok": True, "value": 5.09, "prev_value": 5.10,
              "change_bp": -1.0, "trade_date": "YYYY-MM-DD"}
    실패 시: {"ok": False, "reason": "..."}
    """
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        return {"ok": False, "reason": "FRED_API_KEY not set"}

    try:
        resp = requests.get(
            FRED_API_URL,
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 10,  # 공휴일 등으로 결측(".")이 섞여도 2개는 건지도록 여유 있게
            },
            timeout=15,
        )
        resp.raise_for_status()
        observations = resp.json().get("observations", [])

        valid = [o for o in observations if o.get("value") not in (None, ".")]
        if len(valid) < 2:
            return {"ok": False, "reason": "insufficient valid observations"}

        latest, prev = valid[0], valid[1]
        latest_value = float(latest["value"])
        prev_value = float(prev["value"])
        change_bp = (latest_value - prev_value) * 100.0

        return {
            "ok": True,
            "value": latest_value,
            "prev_value": prev_value,
            "change_bp": change_bp,
            "trade_date": latest["date"],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("FRED fetch failed for %s: %s", series_id, exc)
        return {"ok": False, "reason": str(exc)}
