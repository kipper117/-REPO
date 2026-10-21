"""
Gmail에 "초안(draft)"만 만든다 — 절대 자동 발송하지 않는다.
OAuth 사용자 인증(본인 Gmail 계정 기준): 최초 1회만 브라우저 로그인하면
토큰이 로컬에 저장되어 이후엔 자동으로 재사용된다.
"""
from __future__ import annotations

import base64
import logging
import os
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from . import config

logger = logging.getLogger(__name__)


def _get_credentials() -> Credentials:
    creds = None
    if os.path.exists(config.GMAIL_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(config.GMAIL_TOKEN_PATH, config.GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(config.GMAIL_CLIENT_SECRET_PATH):
                raise FileNotFoundError(
                    f"Gmail OAuth client secret 파일이 없습니다: {config.GMAIL_CLIENT_SECRET_PATH}\n"
                    "Google Cloud Console에서 OAuth 클라이언트 ID(데스크톱 앱)를 만들어 다운로드한 뒤 "
                    "이 경로에 저장해주세요."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GMAIL_CLIENT_SECRET_PATH, config.GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)

        os.makedirs(os.path.dirname(config.GMAIL_TOKEN_PATH), exist_ok=True)
        with open(config.GMAIL_TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return creds


def create_draft(subject: str, body: str, to: str = "") -> dict:
    """
    성공: {"ok": True, "draft_id": "..."}
    실패: {"ok": False, "reason": "..."}
    수신자(to)를 비워두면 Gmail에서 열었을 때 직접 입력하면 된다 (검수 후 발송 전제).
    """
    try:
        creds = _get_credentials()
        service = build("gmail", "v1", credentials=creds)

        message = MIMEText(body)
        message["subject"] = subject
        if to:
            message["to"] = to

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft = service.users().drafts().create(
            userId="me", body={"message": {"raw": raw}}
        ).execute()

        return {"ok": True, "draft_id": draft.get("id")}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gmail draft creation failed: %s", exc)
        return {"ok": False, "reason": str(exc)}
