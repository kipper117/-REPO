"""채권 섹션(금리 줄들) 생성. snapshot.json의 rates(FRED 단일 소스)만 사용.
주식 문자와 합쳐서 한 통으로 보내므로 날짜 헤더는 여기서 반복하지 않는다.
"""
from __future__ import annotations

from . import common

_RATE_LABELS = [
    ("US10Y", "美 10년물 국채금리"),
    ("US30Y", "美 30년물 국채금리"),
]


def build_bond_section(snapshot: dict) -> str | None:
    """
    금리 줄들만 돌려준다. 성공한 금리가 하나도 없으면 None
    (호출부가 섹션 자체를 통째로 생략할 수 있도록).
    """
    lines = ["[美 채권 시황]"]
    has_any = False

    for key, label in _RATE_LABELS:
        rate = snapshot["rates"].get(key, {})
        if rate.get("ok"):
            has_any = True
            lines.append(
                f"{common.arrow_for_bp(rate['change_bp'])} {label} "
                f"{rate['value']:.2f}% ({common.format_bp(rate['change_bp'])})"
            )
    # 실패한 금리는 해당 줄만 생략된다 (telegram_sender가 별도로 경고 전송).

    return "\n".join(lines) if has_any else None
