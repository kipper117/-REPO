"""
구글 스프레드시트 기록 (두 탭 구조):
- "Data" 탭: 모든 수치를 롱포맷(날짜별 1행씩)으로 매일 누적 기록 — 분석/피벗/차트용 원본이자
  "전주비" 계산을 위한 히스토리 소스.
- "Dashboard" 탭: 그날 스냅샷 전체를 증권사 "Market Daily" 스타일 한 장표로 보여준다.
  매번 통째로 다시 그린다(덮어쓰기). 전일비/전주비는 양수=빨강, 음수=파랑 글자색.
snapshot.json과 동일한 값만 쓴다 (별도 API 재호출 없음 -> 값 불일치 방지).
실패해도 텔레그램 발송 자체는 막지 않는다 (실패는 호출부가 경고로 보고한다).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

DATA_HEADER = ["날짜", "구분", "티커", "항목명", "섹터", "값", "등락률(%)", "등락(bp)"]

# 증권사 "Market Daily" 표 관례: 상승=빨강, 하락=파랑
POSITIVE_COLOR = {"red": 0.8, "green": 0.1, "blue": 0.1}    # 빨강 (상승)
NEGATIVE_COLOR = {"red": 0.1, "green": 0.3, "blue": 0.85}   # 파랑 (하락)
HEADER_BG = {"red": 0.85, "green": 0.8, "blue": 0.68}       # 연한 베이지 (헤더/제목 바탕)

_RATE_LABELS = [("US10Y", "美10년물"), ("US30Y", "美30년물")]


def _get_client_and_sheet_id():
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not creds_json or not sheet_id:
        return None, None
    info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    return gspread.authorize(creds), sheet_id


def _get_or_create_worksheet(sh, title: str, rows: int = 1000, cols: int = 10):
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows=rows, cols=cols)


def _already_logged(ws, trade_date: str) -> bool:
    """A열(날짜)에 이미 같은 거래일이 있으면 True (재실행 시 중복 기록 방지)."""
    col = ws.col_values(1)
    return trade_date in col[1:]


# ---------------------------------------------------------------------------
# Data 탭: 롱포맷 누적
# ---------------------------------------------------------------------------
def _append_data_rows(ws_data, snapshot: dict) -> dict:
    if not ws_data.get_all_values():
        ws_data.append_row(DATA_HEADER)

    trade_date = snapshot["trade_date"]
    if _already_logged(ws_data, trade_date):
        logger.info("Data tab already has a row for %s, skipping append", trade_date)
        return {"skipped": True}

    rows: list[list] = []
    idx = snapshot["indices"]
    for name in ("S&P500", "NASDAQ", "DOW"):
        e = idx.get(name, {})
        if e.get("ok"):
            rows.append([trade_date, "지수", "", name, "", e["value"], round(e["change_pct"], 2), ""])

    dxy = idx.get("DXY", {})
    if dxy.get("ok"):
        rows.append([trade_date, "환율", "", "달러인덱스", "", dxy["value"], round(dxy["change_pct"], 2), ""])
    fx = snapshot.get("fx", {}).get("USDKRW", {})
    if fx.get("ok"):
        rows.append([trade_date, "환율", "", "원/달러", "", fx["value"], round(fx["change_pct"], 2), ""])

    for key, label in _RATE_LABELS:
        r = snapshot["rates"].get(key, {})
        if r.get("ok"):
            rows.append([trade_date, "금리", "", label, "", r["value"], "", round(r["change_bp"])])

    for s in snapshot["top20_stocks"]:
        if s.get("ok"):
            rows.append(
                [trade_date, "종목", s["ticker"], s["name_kr"], s["sector"],
                 s["value"], round(s["change_pct"], 2), ""]
            )

    if rows:
        ws_data.append_rows(rows, value_input_option="USER_ENTERED")
    return {"skipped": False, "row_count": len(rows)}


# ---------------------------------------------------------------------------
# 전주비 계산용: Data 탭 히스토리 로드
# ---------------------------------------------------------------------------
def _load_history(ws_data) -> dict[str, list[tuple[str, float]]]:
    """{항목 키(티커 또는 항목명): [(날짜, 값), ...]}"""
    values = ws_data.get_all_values()
    if len(values) < 2:
        return {}

    header = values[0]
    try:
        i_date, i_ticker, i_name, i_value = (
            header.index("날짜"), header.index("티커"), header.index("항목명"), header.index("값"),
        )
    except ValueError:
        return {}

    history: dict[str, list[tuple[str, float]]] = {}
    for row in values[1:]:
        if len(row) <= i_value:
            continue
        key = row[i_ticker] or row[i_name]
        date_str, val_str = row[i_date], row[i_value]
        if not key or not date_str or not val_str:
            continue
        try:
            history.setdefault(key, []).append((date_str, float(val_str)))
        except ValueError:
            continue
    return history


def _week_ago_value(history: dict, key: str, trade_date: str, lookback_days: int = 7) -> float | None:
    """trade_date 기준 lookback_days 이전 시점에 가장 가까운(그 이전 중 최신) 값."""
    try:
        target = datetime.strptime(trade_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    cutoff = target - timedelta(days=lookback_days)
    candidates = [
        (d, v) for d, v in history.get(key, [])
        if _safe_date(d) is not None and _safe_date(d) <= cutoff
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0])
    return candidates[-1][1]


def _safe_date(date_str: str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Dashboard 탭: "Market Daily" 스타일 한 장표, 매번 덮어쓰기
# ---------------------------------------------------------------------------
def _fmt_pct(value: float | None) -> str:
    if value is None:
        return ""
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def _fmt_bp(value: float | None) -> str:
    if value is None:
        return ""
    sign = "+" if value > 0 else ""
    return f"{sign}{round(value)}bp"


def _rebuild_dashboard(ws, snapshot: dict, history: dict) -> None:
    ws.clear()

    trade_date = snapshot["trade_date"]
    dt = datetime.strptime(trade_date, "%Y-%m-%d")
    title = f"Market Daily({dt.month}/{dt.day})"

    grid: list[list] = []
    color_cells: list[tuple[int, int, bool]] = []  # (1-idx row, 1-idx col, is_positive)
    header_cells: list[tuple[int, int, int]] = []  # (1-idx row, start col, end col exclusive)

    def row_idx() -> int:
        return len(grid)

    def mark(col_1idx: int, value: float | None) -> None:
        if value is not None:
            color_cells.append((row_idx(), col_1idx, value >= 0))

    # --- 제목 ---
    grid.append([title])
    header_cells.append((1, 1, 9))
    grid.append([])

    # --- 지수 | 환율·금리 (좌우 2단 배치) ---
    idx = snapshot["indices"]
    rates = snapshot["rates"]
    fx = snapshot.get("fx", {})

    left_items = [("S&P500", idx.get("S&P500", {}), "pct"),
                  ("NASDAQ", idx.get("NASDAQ", {}), "pct"),
                  ("DOW", idx.get("DOW", {}), "pct")]
    right_items = [("달러인덱스", idx.get("DXY", {}), "pct"),
                   ("원/달러", fx.get("USDKRW", {}), "pct"),
                   ("美10년물", rates.get("US10Y", {}), "rate"),
                   ("美30년물", rates.get("US30Y", {}), "rate")]

    grid.append(["지수", "종가", "전일비", "전주비", "", "환율/금리", "종가", "전일비", "전주비"])
    header_cells.append((row_idx(), 1, 9))

    for i in range(max(len(left_items), len(right_items))):
        row = ["", "", "", "", "", "", "", "", ""]
        if i < len(left_items):
            name, e, kind = left_items[i]
            if e.get("ok"):
                key = name
                day_val = e["change_pct"]
                week_base = _week_ago_value(history, key, trade_date)
                week_pct = ((e["value"] - week_base) / week_base * 100.0) if week_base else None
                row[0:4] = [name, round(e["value"], 2), _fmt_pct(day_val), _fmt_pct(week_pct)]
        if i < len(right_items):
            name, e, kind = right_items[i]
            if e.get("ok"):
                key = name
                if kind == "rate":
                    day_val = e["change_bp"]
                    week_base = _week_ago_value(history, key, trade_date)
                    week_val = (e["value"] - week_base) * 100.0 if week_base is not None else None
                    row[5:9] = [name, round(e["value"], 2), _fmt_bp(day_val), _fmt_bp(week_val)]
                else:
                    day_val = e["change_pct"]
                    week_base = _week_ago_value(history, key, trade_date)
                    week_val = ((e["value"] - week_base) / week_base * 100.0) if week_base else None
                    row[5:9] = [name, round(e["value"], 2), _fmt_pct(day_val), _fmt_pct(week_val)]
        grid.append(row)
        if i < len(left_items) and left_items[i][1].get("ok"):
            mark(3, left_items[i][1]["change_pct"])
            wb = _week_ago_value(history, left_items[i][0], trade_date)
            if wb:
                mark(4, left_items[i][1]["value"] - wb)
        if i < len(right_items) and right_items[i][1].get("ok"):
            name, e, kind = right_items[i]
            val = e["change_bp"] if kind == "rate" else e["change_pct"]
            mark(8, val)
            wb = _week_ago_value(history, name, trade_date)
            if wb is not None:
                mark(9, e["value"] - wb)

    grid.append([])

    # --- 시총 상위 종목 ---
    grid.append(["종목명", "티커", "섹터", "종가", "전일비", "전주비"])
    header_cells.append((row_idx(), 1, 6))

    for s in snapshot["top20_stocks"]:
        if not s.get("ok"):
            continue
        week_base = _week_ago_value(history, s["ticker"], trade_date)
        week_pct = ((s["value"] - week_base) / week_base * 100.0) if week_base else None
        grid.append([
            s["name_kr"], s["ticker"], s["sector"],
            round(s["value"], 2), _fmt_pct(s["change_pct"]), _fmt_pct(week_pct),
        ])
        mark(5, s["change_pct"])
        mark(6, week_pct)

    ws.update(range_name="A1", values=grid)

    requests = []
    # 제목/헤더 행: 굵게 + 베이지 배경 (+ 제목은 가운데 정렬·병합)
    for row_1idx, start_col, end_col in header_cells:
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": ws.id,
                    "startRowIndex": row_1idx - 1, "endRowIndex": row_1idx,
                    "startColumnIndex": start_col - 1, "endColumnIndex": end_col,
                },
                "cell": {"userEnteredFormat": {
                    "backgroundColor": HEADER_BG,
                    "textFormat": {"bold": True},
                    "horizontalAlignment": "CENTER",
                }},
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        })
    requests.append({
        "mergeCells": {
            "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": 9},
            "mergeType": "MERGE_ALL",
        }
    })
    # 등락 셀: 상승=빨강, 하락=파랑
    for row_1idx, col_1idx, is_positive in color_cells:
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": ws.id,
                    "startRowIndex": row_1idx - 1, "endRowIndex": row_1idx,
                    "startColumnIndex": col_1idx - 1, "endColumnIndex": col_1idx,
                },
                "cell": {"userEnteredFormat": {"textFormat": {
                    "foregroundColor": POSITIVE_COLOR if is_positive else NEGATIVE_COLOR,
                    "bold": True,
                }}},
                "fields": "userEnteredFormat.textFormat",
            }
        })

    if requests:
        ws.spreadsheet.batch_update({"requests": requests})


def append_snapshot(snapshot: dict) -> dict:
    """
    성공: {"ok": True} (Data 탭에 이미 그 날짜가 있으면 {"ok": True, "skipped": True})
    실패: {"ok": False, "reason": "..."}
    """
    try:
        gc, sheet_id = _get_client_and_sheet_id()
        if not gc:
            return {"ok": False, "reason": "GOOGLE_SERVICE_ACCOUNT_JSON / GOOGLE_SHEET_ID not set"}

        sh = gc.open_by_key(sheet_id)
        ws_data = _get_or_create_worksheet(sh, "Data", cols=len(DATA_HEADER))

        # 전주비 계산은 이번에 추가되는 오늘자 행 이전의 히스토리만 써야 하므로 append 전에 로드한다.
        history = _load_history(ws_data)
        data_result = _append_data_rows(ws_data, snapshot)

        ws_dashboard = _get_or_create_worksheet(sh, "Dashboard", rows=80, cols=9)
        _rebuild_dashboard(ws_dashboard, snapshot, history)

        return {"ok": True, "skipped": data_result.get("skipped", False)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google Sheets update failed: %s", exc)
        return {"ok": False, "reason": str(exc)}
