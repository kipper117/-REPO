"""
Claude로 리포트 묶음을 고객 발송용 시황 메일 "본문 요약부"만 생성한다.
인사말/마무리/서명은 코드(= config)가 붙인다 — 연락처 등 정확해야 하는 값을
Claude가 지어내거나 바꿔 쓰지 않도록 하기 위함 (시황봇과 동일한 원칙).
"""
from __future__ import annotations

import logging
import os

import anthropic

from . import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
너는 증권사 PB가 고객에게 보내는 시황/산업 리포트 요약 메일의 "본문 요약부"를 작성하는 보조 작성자다.
입력으로 여러 증권사 리포트의 제목과 본문 텍스트가 주어진다.

반드시 지켜야 할 규칙:
1. 리포트에 실제로 쓰여 있지 않은 수치나 사실을 지어내지 마라.
2. 각 요약에는 어느 증권사 리포트인지 출처를 명시하라 (예: "OO증권에 따르면~").
3. 원 리포트의 분석/전망은 간접화법으로 전달하라 (예: "~라고 전망했다", "~라고 분석했다").
   너 자신의 매수/매도 의견이나 투자 권유 문구를 새로 추가하지 마라.
4. 정중한 한국어 존댓말(합니다체)로, 고객에게 보내는 정식 업무 메일 톤으로 써라.
5. 리포트가 3개 이하면 리포트별로 소제목(■ 또는 숫자)을 나눠 작성하는 것을 권장한다.
6. 반드시 아래 형식으로만 출력하라. 다른 설명은 절대 덧붙이지 마라.

제목: <메일 제목, 간결하게>
---
<본문 요약부. 인사말이나 마무리 인사, 서명은 쓰지 마라 — 그건 별도로 붙는다.>
"""


def compose(reports: list[dict]) -> dict:
    """
    성공: {"ok": True, "subject": "...", "body": "..."}
    실패: {"ok": False, "reason": "..."}
    """
    usable = [r for r in reports if r.get("text", "").strip()]
    if not usable:
        return {"ok": False, "reason": "추출된 텍스트가 있는 리포트가 없습니다."}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"ok": False, "reason": "ANTHROPIC_API_KEY not set"}

    report_blocks = []
    for r in usable:
        report_blocks.append(f"[{r['source']}] {r['title']}\n{r['text']}")
    user_prompt = "\n\n=====\n\n".join(report_blocks)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = response.content[0].text.strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Claude email composition failed: %s", exc)
        return {"ok": False, "reason": str(exc)}

    if "제목:" not in text or "---" not in text:
        return {"ok": False, "reason": f"예상 형식과 다른 응답: {text[:200]}"}

    subject_part, _, body_part = text.partition("---")
    subject = subject_part.split("제목:", 1)[1].strip()
    body = body_part.strip()
    return {"ok": True, "subject": subject, "body": body}


def build_full_email(subject: str, summary_body: str) -> dict:
    """인사말 + Claude 요약부 + 마무리/서명을 합쳐 최종 메일 제목/본문을 만든다."""
    greeting = f"안녕하십니까,\n{config.SENDER_GREETING_LINE}"
    closing = (
        "추후 또 업데이트 드리겠습니다.\n"
        "감사합니다.\n\n"
        f"{config.SENDER_TITLE}\n"
        f"{config.OFFICE_PHONE}\n"
        f"{config.MOBILE_PHONE}"
    )
    full_body = f"{greeting}\n\n{summary_body}\n\n{closing}"
    return {"subject": subject, "body": full_body}
