"""
구글 시트 "Data" 탭(읽기 전용)을 로컬에서 읽어 전주비 계산에 쓴다.
계산 로직 자체는 src/sheets_writer.py의 것을 그대로 재사용한다 (중복 방지).
설정이 없거나 실패하면 빈 히스토리를 돌려주고, 호출부는 전주비 없이 진행하면 된다.
"""
from __future__ import annotations

import json
import logging
import os

import gspread
from google.oauth2.service_account import Credentials

from . import config

try:
    from src.sheets_writer import _load_history, _week_ago_value
except ImportError:  # repo 루트가 sys.path에 없는 환경 대비
    _load_history = None
    _week_ago_value = None

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

week_ago_value = _week_ago_value


def load_history() -> dict:
    """{항목 키(티커 또는 항목명): [(날짜, 값), ...]}. 실패하면 빈 dict."""
    if _load_history is None:
        return {}
    if not config.GOOGLE_SHEET_ID or not os.path.exists(config.GOOGLE_SERVICE_ACCOUNT_PATH):
        logger.info("Google Sheet history not configured, skipping 전주비")
        return {}
    try:
        with open(config.GOOGLE_SERVICE_ACCOUNT_PATH, encoding="utf-8") as f:
            info = json.load(f)
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(config.GOOGLE_SHEET_ID)
        ws = sh.worksheet("Data")
        return _load_history(ws)
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed to load sheet history: %s", exc)
        return {}
