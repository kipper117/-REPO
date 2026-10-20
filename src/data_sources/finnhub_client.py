"""
Finnhub에서 일반 시황 뉴스 헤드라인을 가져온다.
이 헤드라인은 문자에 직접 들어가지 않고, Claude의 "한 줄 코멘트" 생성 시
맥락(지금 왜 이런 흐름인지)을 주기 위한 참고 자료로만 쓴다.
"""
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/news"


def fetch_market_headlines(category: str = "general", limit: int = 5) -> dict:
    """
    성공 시: {"ok": True, "headlines": ["...", "..."]}
    실패 시: {"ok": False, "reason": "..."}
    """
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        return {"ok": False, "reason": "FINNHUB_API_KEY not set"}

    try:
        resp = requests.get(
            FINNHUB_NEWS_URL,
            params={"category": category, "token": api_key},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json()
        headlines = [item["headline"] for item in items[:limit] if item.get("headline")]
        if not headlines:
            return {"ok": False, "reason": "no headlines returned"}
        return {"ok": True, "headlines": headlines}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Finnhub fetch failed: %s", exc)
        return {"ok": False, "reason": str(exc)}
