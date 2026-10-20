"""포맷터 공통 유틸: 날짜 표기, bp 표기, 강세/약세 라벨 계산."""
from __future__ import annotations

from datetime import datetime

from .. import config

_WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def format_trade_date_header(trade_date: str) -> str:
    """'2026-10-16' -> '10/16(금) 마감'"""
    dt = datetime.strptime(trade_date, "%Y-%m-%d")
    weekday = _WEEKDAY_KO[dt.weekday()]
    return f"{dt.month}/{dt.day}({weekday}) 마감"


def format_bp(change_bp: float) -> str:
    """-1.0 -> '-1bp', 2.0 -> '+2bp'"""
    rounded = round(change_bp)
    sign = "+" if rounded > 0 else ""  # 음수는 '-'가 이미 붙어 나옴
    return f"{sign}{rounded}bp"


def format_pct(change_pct: float) -> str:
    sign = "+" if change_pct > 0 else ""
    return f"{sign}{change_pct:.2f}%"


def arrow_for_pct(change_pct: float, flat_threshold: float = 0.02) -> str:
    """등락률 기준 화살표. ±flat_threshold(%) 이내는 보합(➖)."""
    if change_pct > flat_threshold:
        return "▲"
    if change_pct < -flat_threshold:
        return "▼"
    return "➖"


def arrow_for_bp(change_bp: float, flat_threshold_bp: float = 0.5) -> str:
    if change_bp > flat_threshold_bp:
        return "▲"
    if change_bp < -flat_threshold_bp:
        return "▼"
    return "➖"


def format_pct_with_arrow(change_pct: float) -> str:
    return f"{arrow_for_pct(change_pct)} {format_pct(change_pct)}"


def format_bp_with_arrow(change_bp: float) -> str:
    return f"{arrow_for_bp(change_bp)} {format_bp(change_bp)}"


def label_for_group(entries: list[dict]) -> str:
    """
    entries: [{"change_pct": float, "ok": True}, ...] (ok=True인 것만 평균 계산)
    그룹 평균 등락률 기준으로 (강세)/(약세)/(혼조) 반환.
    """
    valid = [e["change_pct"] for e in entries if e.get("ok")]
    if not valid:
        return "(데이터 없음)"
    avg = sum(valid) / len(valid)
    if avg > config.LABEL_THRESHOLD_PCT:
        return "(강세)"
    if avg < -config.LABEL_THRESHOLD_PCT:
        return "(약세)"
    return "(혼조)"
