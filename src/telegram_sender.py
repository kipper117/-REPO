"""텔레그램 발송. 본문 메시지와, 데이터 실패/이상치 경고 메시지를 분리해서 보낸다."""
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def _send(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set, cannot send")
        return False

    try:
        resp = requests.post(
            TELEGRAM_API_URL.format(token=token),
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Telegram send failed: %s", exc)
        return False


def send_briefing(text: str) -> bool:
    return _send(text)


def send_warning(failures: list[dict], anomalies: list[dict]) -> bool:
    """
    실패/이상치 내역을 본문과 별도의 경고 메시지로 보낸다.
    failures/anomalies가 비어있으면 아무것도 보내지 않는다.
    """
    if not failures and not anomalies:
        return True

    lines = ["[시황봇 경고]"]
    if failures:
        lines.append("")
        lines.append("조회 실패:")
        for f in failures:
            lines.append(f"- {f['item']}: {f.get('reason')}")
    if anomalies:
        lines.append("")
        lines.append("이상치 감지:")
        for a in anomalies:
            lines.append(f"- {a['item']} ({a['kind']}): {a['value']}")

    return _send("\n".join(lines))


def send_abort_notice(reason: str) -> bool:
    return _send(f"[시황봇 발송 중단]\n{reason}")
