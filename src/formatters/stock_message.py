"""주식 시황 문자 생성. snapshot.json 값만 사용 (직접 API 호출 금지)."""
from __future__ import annotations

from .. import config
from . import common


def build_stock_section(snapshot: dict) -> str:
    header = common.format_trade_date_header(snapshot["trade_date"])
    lines = [f"[美 증시 시황] {header}", ""]

    # 주요 지수 (실패한 항목은 섹션에서 통째로 생략)
    index_entries = [
        snapshot["indices"][name]
        for name in ("S&P500", "NASDAQ", "DOW")
        if snapshot["indices"].get(name, {}).get("ok")
    ]
    if index_entries:
        lines.append(f"■ 주요 지수 {common.label_for_group(index_entries)}")
        for name in ("S&P500", "NASDAQ", "DOW"):
            result = snapshot["indices"].get(name, {})
            if result.get("ok"):
                lines.append(
                    f"  {name} {result['value']:,.2f} {common.format_pct_with_arrow(result['change_pct'])}"
                )

    # 달러인덱스
    dxy = snapshot["indices"].get("DXY", {})
    if dxy.get("ok"):
        lines.append("")
        lines.append(f"■ 달러인덱스 {dxy['value']:,.2f} {common.format_pct_with_arrow(dxy['change_pct'])}")

    # 시가총액 상위 종목: 섹터별로 묶어서 표시
    top20_ok = [s for s in snapshot["top20_stocks"] if s.get("ok")]
    if top20_ok:
        lines.append("")
        lines.append(f"[시총 상위 종목] {common.label_for_group(top20_ok)}")
        by_sector: dict[str, list[dict]] = {}
        for s in top20_ok:
            by_sector.setdefault(s["sector"], []).append(s)

        for sector in config.SECTOR_ORDER:
            entries = by_sector.get(sector)
            if not entries:
                continue
            lines.append("")
            lines.append(f"▸ {sector} {common.label_for_group(entries)}")
            for s in entries:
                lines.append(
                    f"  {common.arrow_for_pct(s['change_pct'])} {s['name_kr']}({s['ticker']}) "
                    f"{s['value']:,.2f} {common.format_pct(s['change_pct'])}"
                )

    return "\n".join(lines)
