"""주식 시황 문자 생성. snapshot.json 값만 사용 (직접 API 호출 금지)."""
from __future__ import annotations

from . import common


def build_stock_message(snapshot: dict, one_line_comment: str | None = None) -> str:
    header = common.format_trade_date_header(snapshot["trade_date"])
    lines = [f"[美 증시 시황] {header}", ""]

    # 주요 지수 (실패한 항목은 섹션에서 통째로 생략)
    index_entries = [
        snapshot["indices"][name]
        for name in ("S&P500", "NASDAQ", "DOW")
        if snapshot["indices"].get(name, {}).get("ok")
    ]
    if index_entries:
        lines.append(f"주요 지수 {common.label_for_group(index_entries)}")
        for name in ("S&P500", "NASDAQ", "DOW"):
            result = snapshot["indices"].get(name, {})
            if result.get("ok"):
                lines.append(f"{name} {result['value']:,.2f} {common.format_pct(result['change_pct'])}")

    # 달러인덱스
    dxy = snapshot["indices"].get("DXY", {})
    if dxy.get("ok"):
        lines.append("")
        lines.append(f"달러인덱스 {dxy['value']:,.2f} {common.format_pct(dxy['change_pct'])}")

    # 시가총액 상위 20개 종목
    top20_ok = [s for s in snapshot["top20_stocks"] if s.get("ok")]
    if top20_ok:
        lines.append("")
        lines.append(f"[시총 상위 종목] {common.label_for_group(top20_ok)}")
        for s in top20_ok:
            lines.append(f"{s['name']}({s['ticker']}) {s['value']:,.2f} {common.format_pct(s['change_pct'])}")

    if one_line_comment:
        lines.append("")
        lines.append(one_line_comment)

    return "\n".join(lines)
