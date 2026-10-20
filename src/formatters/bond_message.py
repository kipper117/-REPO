"""채권 시황 문자 생성. 금리는 snapshot.json의 rates(FRED 단일 소스)만 사용."""
from __future__ import annotations

from . import common


def build_bond_message(snapshot: dict, one_line_comment: str | None = None) -> str:
    header = common.format_trade_date_header(snapshot["trade_date"])
    lines = [f"[美 채권 시황] {header}", ""]

    us10y = snapshot["rates"].get("US10Y", {})
    if us10y.get("ok"):
        lines.append(f"美 10년물 국채금리 {us10y['value']:.2f}% ({common.format_bp(us10y['change_bp'])})")
    # 실패 시 이 섹션은 통째로 생략된다 (telegram_sender가 별도로 경고 전송).

    if one_line_comment:
        lines.append("")
        lines.append(one_line_comment)

    return "\n".join(lines)
