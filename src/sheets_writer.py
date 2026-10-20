"""
구글 스프레드시트에 매일 데이터를 누적 기록한다.
- "지수_금리" 탭: 날짜별 1행 (지수/달러인덱스/금리 요약)
- "종목" 탭: 날짜×종목별 1행 (시총 상위 종목 롱포맷, 피벗/차트용)
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

INDEX_RATE_HEADER = [
    "날짜",
    "S&P500", "S&P500 등락률(%)",
    "NASDAQ", "NASDAQ 등락률(%)",
    "DOW", "DOW 등락률(%)",
    "달러인덱스", "달러인덱스 등락률(%)",
    "美10년물(%)", "美10년물 bp",
    "美30년물(%)", "美30년물 bp",
]
STOCK_HEADER = ["날짜", "티커", "종목명", "섹터", "종가", "등락률(%)"]


def _get_client_and_sheet_id():
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not creds_json or not sheet_id:
        return None, None
    info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    return gspread.authorize(creds), sheet_id


def _get_or_create_worksheet(sh, title: str, header: list[str]):
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=len(header))
        ws.append_row(header)
        return ws
    if not ws.get_all_values():
        ws.append_row(header)
    return ws


def _already_logged(ws, trade_date: str) -> bool:
    """A열(날짜)에 이미 같은 거래일이 있으면 True (재실행 시 중복 기록 방지)."""
    col = ws.col_values(1)
    return trade_date in col[1:]


def _val(entry: dict, key: str):
    return entry.get(key) if entry.get("ok") else ""


def append_snapshot(snapshot: dict) -> dict:
    """
    성공: {"ok": True} (혹은 이미 기록된 날짜면 {"ok": True, "skipped": True})
    실패: {"ok": False, "reason": "..."}
    """
    try:
        gc, sheet_id = _get_client_and_sheet_id()
        if not gc:
            return {"ok": False, "reason": "GOOGLE_SERVICE_ACCOUNT_JSON / GOOGLE_SHEET_ID not set"}

        sh = gc.open_by_key(sheet_id)
        trade_date = snapshot["trade_date"]

        ws_idx = _get_or_create_worksheet(sh, "지수_금리", INDEX_RATE_HEADER)
        if _already_logged(ws_idx, trade_date):
            logger.info("sheet already has a row for %s, skipping", trade_date)
            return {"ok": True, "skipped": True}

        idx = snapshot["indices"]
        rates = snapshot["rates"]
        row = [
            trade_date,
            _val(idx.get("S&P500", {}), "value"), _val(idx.get("S&P500", {}), "change_pct"),
            _val(idx.get("NASDAQ", {}), "value"), _val(idx.get("NASDAQ", {}), "change_pct"),
            _val(idx.get("DOW", {}), "value"), _val(idx.get("DOW", {}), "change_pct"),
            _val(idx.get("DXY", {}), "value"), _val(idx.get("DXY", {}), "change_pct"),
            _val(rates.get("US10Y", {}), "value"), _val(rates.get("US10Y", {}), "change_bp"),
            _val(rates.get("US30Y", {}), "value"), _val(rates.get("US30Y", {}), "change_bp"),
        ]
        ws_idx.append_row(row, value_input_option="USER_ENTERED")

        ws_stocks = _get_or_create_worksheet(sh, "종목", STOCK_HEADER)
        stock_rows = [
            [trade_date, s["ticker"], s["name_kr"], s["sector"], s["value"], s["change_pct"]]
            for s in snapshot["top20_stocks"]
            if s.get("ok")
        ]
        if stock_rows:
            ws_stocks.append_rows(stock_rows, value_input_option="USER_ENTERED")

        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google Sheets append failed: %s", exc)
        return {"ok": False, "reason": str(exc)}
