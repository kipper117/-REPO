"""
구글 스프레드시트 기록 (두 탭 구조):
- "Data" 탭: 모든 수치를 롱포맷(날짜별 1행씩)으로 매일 누적 기록 — 분석/피벗/차트용 원본.
- "Dashboard" 탭: 그날 스냅샷 전체를 한 장표로 보여주는 대시보드.
  매번 통째로 다시 그린다(덮어쓰기). 등락률/bp 셀은 양수=초록, 음수=파랑 글자색으로 표시.
snapshot.json과 동일한 값만 쓴다 (별도 API 재호출 없음 -> 값 불일치 방지).
실패해도 텔레그램 발송 자체는 막지 않는다 (실패는 호출부가 경고로 보고한다).
"""
from __future__ import annotations

import json
import logging
import os

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

DATA_HEADER = ["날짜", "구분", "티커", "항목명", "섹터", "값", "등락률(%)", "등락(bp)"]

POSITIVE_COLOR = {"red": 0.0, "green": 0.45, "blue": 0.05}   # 초록 (상승)
NEGATIVE_COLOR = {"red": 0.05, "green": 0.3, "blue": 0.85}   # 파랑 (하락)

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


def _val(entry: dict, key: str):
    return entry.get(key) if entry.get("ok") else ""


# ---------------------------------------------------------------------------
# Data 탭: 롱포맷 누적
# ---------------------------------------------------------------------------
def _append_data_rows(sh, snapshot: dict) -> dict:
    ws = _get_or_create_worksheet(sh, "Data", cols=len(DATA_HEADER))
    if not ws.get_all_values():
        ws.append_row(DATA_HEADER)

    trade_date = snapshot["trade_date"]
    if _already_logged(ws, trade_date):
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
        ws.append_rows(rows, value_input_option="USER_ENTERED")
    return {"skipped": False, "row_count": len(rows)}


# ---------------------------------------------------------------------------
# Dashboard 탭: 한 장표, 매번 덮어쓰기
# ---------------------------------------------------------------------------
def _rebuild_dashboard(sh, snapshot: dict) -> None:
    ws = _get_or_create_worksheet(sh, "Dashboard", rows=60, cols=6)
    ws.clear()

    trade_date = snapshot["trade_date"]
    values: list[list] = []
    color_cells: list[tuple[int, int, bool]] = []  # (1-indexed row, 1-indexed col, is_positive)

    def add_row(cells: list) -> None:
        values.append(cells)

    def mark_color(col_1idx: int, is_positive: bool) -> None:
        color_cells.append((len(values), col_1idx, is_positive))

    add_row([f"美 증시/채권 시황 대시보드 — {trade_date} 마감"])
    add_row([])

    add_row(["[주요 지수]", "값", "등락률(%)"])
    for name in ("S&P500", "NASDAQ", "DOW"):
        e = snapshot["indices"].get(name, {})
        if e.get("ok"):
            add_row([name, round(e["value"], 2), round(e["change_pct"], 2)])
            mark_color(3, e["change_pct"] >= 0)
    add_row([])

    add_row(["[환율]", "값", "등락률(%)"])
    dxy = snapshot["indices"].get("DXY", {})
    if dxy.get("ok"):
        add_row(["달러인덱스", round(dxy["value"], 2), round(dxy["change_pct"], 2)])
        mark_color(3, dxy["change_pct"] >= 0)
    fx = snapshot.get("fx", {}).get("USDKRW", {})
    if fx.get("ok"):
        add_row(["원/달러", round(fx["value"], 2), round(fx["change_pct"], 2)])
        mark_color(3, fx["change_pct"] >= 0)
    add_row([])

    add_row(["[국채금리]", "값(%)", "등락(bp)"])
    for key, label in _RATE_LABELS:
        r = snapshot["rates"].get(key, {})
        if r.get("ok"):
            add_row([label, round(r["value"], 2), round(r["change_bp"])])
            mark_color(3, r["change_bp"] >= 0)
    add_row([])

    add_row(["[시총 상위 종목]", "티커", "섹터", "종가", "등락률(%)"])
    for s in snapshot["top20_stocks"]:
        if s.get("ok"):
            add_row([s["name_kr"], s["ticker"], s["sector"], round(s["value"], 2), round(s["change_pct"], 2)])
            mark_color(5, s["change_pct"] >= 0)

    if values:
        ws.update(range_name="A1", values=values)

    requests = [
        {
            "repeatCell": {
                "range": {
                    "sheetId": ws.id,
                    "startRowIndex": row_1idx - 1,
                    "endRowIndex": row_1idx,
                    "startColumnIndex": col_1idx - 1,
                    "endColumnIndex": col_1idx,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {
                            "foregroundColor": POSITIVE_COLOR if is_positive else NEGATIVE_COLOR,
                            "bold": True,
                        }
                    }
                },
                "fields": "userEnteredFormat.textFormat",
            }
        }
        for row_1idx, col_1idx, is_positive in color_cells
    ]
    if requests:
        sh.batch_update({"requests": requests})


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
        data_result = _append_data_rows(sh, snapshot)
        _rebuild_dashboard(sh, snapshot)

        return {"ok": True, "skipped": data_result.get("skipped", False)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google Sheets update failed: %s", exc)
        return {"ok": False, "reason": str(exc)}
