"""
메일 본문에 바로 넣을 수 있는 HTML 표(대시보드 요약) + 상단 하이라이트 박스를 만든다.
구글 시트 Dashboard 탭과 같은 데이터/색상 관례(상승=빨강, 하락=파랑)를 쓰되,
이메일 너비(약 640px)에 맞춰 섹션을 세로로 쌓는 레이아웃으로 구성한다
(메일 클라이언트는 flex/grid 지원이 들쭉날쭉해서 가로 3단보다 안정적).

history가 주어지면(= 구글 시트 Data 탭 읽기 성공) "전주비" 열도 추가한다.
history가 없거나 아직 일주일치가 안 쌓였으면 그 칸은 그냥 빈 채로 나온다.
"""
from __future__ import annotations

from datetime import datetime

POSITIVE = "#c0392b"  # 빨강 (상승)
NEGATIVE = "#1a56db"  # 파랑 (하락)
HEADER_BG = "#ded6c3"
ROW_ALT_BG = "#f7f5f0"
BORDER = "#d9d3c4"

_TABLE_STYLE = (
    f"border-collapse:collapse;width:100%;max-width:640px;"
    f"font-family:Arial,'맑은 고딕',sans-serif;font-size:13px;margin-bottom:18px;"
)
_TH_STYLE = (
    f"background:{HEADER_BG};border:1px solid {BORDER};padding:6px 8px;"
    f"text-align:left;font-weight:bold;"
)
_TD_STYLE = f"border:1px solid {BORDER};padding:5px 8px;"


def _fmt_pct(v: float) -> str:
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.2f}%"


def _fmt_bp(v: float) -> str:
    sign = "+" if v > 0 else ""
    return f"{sign}{round(v)}bp"


def _change_cell(formatted: str, is_positive: bool) -> str:
    if not formatted:
        return f'<td style="{_TD_STYLE}color:#999;">-</td>'
    color = POSITIVE if is_positive else NEGATIVE
    return f'<td style="{_TD_STYLE}color:{color};font-weight:bold;">{formatted}</td>'


def _section_table(title: str, col_headers: list[str], rows_html: list[str]) -> str:
    thead = "".join(f'<th style="{_TH_STYLE}">{h}</th>' for h in col_headers)
    body = "".join(rows_html)
    return (
        f'<h3 style="font-family:Arial,sans-serif;font-size:14px;margin:4px 0;">{title}</h3>'
        f'<table style="{_TABLE_STYLE}">'
        f"<tr>{thead}</tr>{body}"
        f"</table>"
    )


def _week_pct(history: dict, key: str, trade_date: str, current_value: float) -> float | None:
    if not history:
        return None
    from email_draft.sheet_history import week_ago_value

    if week_ago_value is None:
        return None
    base = week_ago_value(history, key, trade_date)
    if not base:
        return None
    return (current_value - base) / base * 100.0


def _week_bp(history: dict, key: str, trade_date: str, current_value: float) -> float | None:
    if not history:
        return None
    from email_draft.sheet_history import week_ago_value

    if week_ago_value is None:
        return None
    base = week_ago_value(history, key, trade_date)
    if base is None:
        return None
    return (current_value - base) * 100.0


def _index_row(name: str, entry: dict, alt: bool, history: dict, trade_date: str) -> str:
    bg = f"background:{ROW_ALT_BG};" if alt else ""
    day = _change_cell(_fmt_pct(entry["change_pct"]), entry["change_pct"] >= 0)
    cells = [f'<td style="{_TD_STYLE}">{name}</td>', f'<td style="{_TD_STYLE}">{entry["value"]:,.2f}</td>', day]
    if history:
        wp = _week_pct(history, name, trade_date, entry["value"])
        cells.append(_change_cell(_fmt_pct(wp) if wp is not None else "", (wp is not None and wp >= 0)))
    return f'<tr style="{bg}">{"".join(cells)}</tr>'


def build_highlight_bar(snapshot: dict) -> str:
    """메일 맨 위에 올릴 3~4개 핵심 지표 하이라이트 박스."""
    idx = snapshot["indices"]
    fx = snapshot.get("fx", {})
    gidx = snapshot.get("global_indices", {})

    candidates = [
        ("코스피", gidx.get("KOSPI")),
        ("다우", idx.get("DOW")),
        ("나스닥", idx.get("NASDAQ")),
        ("원/달러", fx.get("USDKRW")),
    ]
    chips = []
    for name, e in candidates:
        if not e or not e.get("ok"):
            continue
        is_pos = e["change_pct"] >= 0
        color = POSITIVE if is_pos else NEGATIVE
        chips.append(
            f'<span style="display:inline-block;margin:0 10px 6px 0;font-size:13px;">'
            f'<b>{name}</b> <span style="color:{color};font-weight:bold;">{_fmt_pct(e["change_pct"])}</span>'
            f"</span>"
        )
    if not chips:
        return ""
    return (
        f'<div style="background:#f3f0e8;border:1px solid {BORDER};border-radius:4px;'
        f'padding:10px 12px;max-width:640px;margin-bottom:16px;font-family:Arial,sans-serif;">'
        + "".join(chips)
        + "</div>"
    )


def build_dashboard_html(snapshot: dict, history: dict | None = None) -> str:
    history = history or {}
    trade_date = snapshot["trade_date"]
    dt = datetime.strptime(trade_date, "%Y-%m-%d")
    idx = snapshot["indices"]
    fx = snapshot.get("fx", {})
    gidx = snapshot.get("global_indices", {})
    comm = snapshot.get("commodities", {})
    rates = snapshot["rates"]

    change_headers = ["전일비", "전주비"] if history else ["전일비"]

    parts = [
        f'<div style="font-family:Arial,sans-serif;">'
        f'<h2 style="font-size:16px;background:{HEADER_BG};padding:8px 10px;margin:0 0 14px 0;'
        f'max-width:640px;">Market Daily ({dt.month}/{dt.day})</h2>'
    ]

    # 미국지수
    us_items = [("S&P500", idx.get("S&P500")), ("NASDAQ", idx.get("NASDAQ")),
                ("DOW", idx.get("DOW")), ("필라델피아반도체", gidx.get("필라델피아반도체"))]
    rows = [_index_row(n, e, i % 2 == 1, history, trade_date)
            for i, (n, e) in enumerate(us_items) if e and e.get("ok")]
    parts.append(_section_table("미국지수", ["지수", "종가", *change_headers], rows))

    # 해외지수
    global_items = [("KOSPI", gidx.get("KOSPI")), ("KOSDAQ", gidx.get("KOSDAQ")),
                     ("니케이225", gidx.get("니케이225")), ("대만가권", gidx.get("대만가권")),
                     ("상해종합", gidx.get("상해종합")), ("심천성분", gidx.get("심천성분")),
                     ("항셍", gidx.get("항셍"))]
    rows = [_index_row(n, e, i % 2 == 1, history, trade_date)
            for i, (n, e) in enumerate(global_items) if e and e.get("ok")]
    parts.append(_section_table("해외지수", ["지수", "종가", *change_headers], rows))

    # 환율/금리/원자재
    fxr_rows = []
    fxr_items = [("달러인덱스", idx.get("DXY")), ("원/달러", fx.get("USDKRW")), ("WTI", comm.get("WTI"))]
    for i, (name, e) in enumerate(fxr_items):
        if e and e.get("ok"):
            fxr_rows.append(_index_row(name, e, i % 2 == 1, history, trade_date))
    rate_items = [("美10년물", rates.get("US10Y")), ("美30년물", rates.get("US30Y"))]
    for i, (name, r) in enumerate(rate_items, start=len(fxr_items)):
        if r and r.get("ok"):
            bg = f"background:{ROW_ALT_BG};" if i % 2 == 1 else ""
            day = _change_cell(_fmt_bp(r["change_bp"]), r["change_bp"] >= 0)
            cells = [f'<td style="{_TD_STYLE}">{name}</td>', f'<td style="{_TD_STYLE}">{r["value"]:.2f}%</td>', day]
            if history:
                wb = _week_bp(history, name, trade_date, r["value"])
                cells.append(_change_cell(_fmt_bp(wb) if wb is not None else "", (wb is not None and wb >= 0)))
            fxr_rows.append(f'<tr style="{bg}">{"".join(cells)}</tr>')
    parts.append(_section_table("환율 · 금리 · 원자재", ["항목", "값", *change_headers], fxr_rows))

    # 시총 상위 종목
    stock_rows = []
    for i, s in enumerate(snapshot["top20_stocks"]):
        if not s.get("ok"):
            continue
        bg = f"background:{ROW_ALT_BG};" if i % 2 == 1 else ""
        day = _change_cell(_fmt_pct(s["change_pct"]), s["change_pct"] >= 0)
        cells = [
            f'<td style="{_TD_STYLE}">{s["name_kr"]}</td>',
            f'<td style="{_TD_STYLE}">{s["ticker"]}</td>',
            f'<td style="{_TD_STYLE}">{s["sector"]}</td>',
            f'<td style="{_TD_STYLE}">{s["value"]:,.2f}</td>',
            day,
        ]
        if history:
            wp = _week_pct(history, s["ticker"], trade_date, s["value"])
            cells.append(_change_cell(_fmt_pct(wp) if wp is not None else "", (wp is not None and wp >= 0)))
        stock_rows.append(f'<tr style="{bg}">{"".join(cells)}</tr>')
    parts.append(
        _section_table("시가총액 상위 종목", ["종목명", "티커", "섹터", "종가", *change_headers], stock_rows)
    )

    parts.append("</div>")
    return "".join(parts)
