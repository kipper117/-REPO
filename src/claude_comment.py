"""
Claude API로 "숫자 없는 한 줄 코멘트"를 만든다.
- 숫자는 전부 템플릿 코드(formatters)가 생성한다. Claude는 코멘트 "문장"만 쓴다.
- 혹시 코멘트에 숫자가 섞여 나오면, snapshot.json의 실제 값과 대조해서
  일치하지 않는 숫자가 하나라도 있으면 코멘트 전체를 버린다(반환값 None).
- 매수/매도 권유, 단정적 전망 표현은 프롬프트에서 명시적으로 금지한다.
"""
from __future__ import annotations

import logging
import os
import re

import anthropic

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")

SYSTEM_PROMPT = """\
너는 증권사 고객에게 보내는 일일 시황 문자에 들어갈 "한 줄 코멘트"를 쓰는 보조 작성자다.
반드시 지켜야 할 규칙:
1. 숫자(등락률, 금리, bp, 주가 등)를 절대 쓰지 마라. 숫자는 다른 코드가 이미 문자에 넣었다.
2. 매수/매도/비중확대/비중축소 등 투자 권유 표현을 쓰지 마라.
3. "내일 오를 것이다" 같은 단정적 전망을 쓰지 마라. 오늘 시장의 흐름/맥락만 담백하게 서술하라.
4. 반드시 한국어 한 문장(40자 내외)으로만 답하라. 다른 설명을 덧붙이지 마라.
"""


def _extract_numbers(text: str) -> list[float]:
    return [float(m) for m in re.findall(r"-?\d+\.?\d*", text)]


def _collect_snapshot_numbers(snapshot: dict) -> set[float]:
    """코멘트 숫자 검증에 쓸, snapshot 안에 실제로 존재하는 숫자들의 집합."""
    numbers: set[float] = set()

    for result in snapshot.get("indices", {}).values():
        if result.get("ok"):
            numbers.add(round(result["value"], 2))
            numbers.add(round(result["change_pct"], 2))

    for stock in snapshot.get("top20_stocks", []):
        if stock.get("ok"):
            numbers.add(round(stock["value"], 2))
            numbers.add(round(stock["change_pct"], 2))

    for rate in snapshot.get("rates", {}).values():
        if rate.get("ok"):
            numbers.add(round(rate["value"], 2))
            numbers.add(round(rate["change_bp"]))

    return numbers


def _comment_numbers_are_valid(comment: str, snapshot: dict) -> bool:
    found = _extract_numbers(comment)
    if not found:
        return True  # 숫자가 아예 없으면 검증 통과 (규칙 1을 Claude가 잘 지킨 경우)

    known = _collect_snapshot_numbers(snapshot)
    for n in found:
        if not any(abs(n - k) < 0.05 for k in known):
            logger.warning("comment contains unverifiable number: %s", n)
            return False
    return True


def generate_one_line_comment(snapshot: dict, news_headlines: list[str] | None = None) -> str | None:
    """
    성공하면 검증된 한 줄 코멘트 문자열을, 실패/검증 불통과면 None을 반환한다.
    None인 경우 호출부는 코멘트 없이 문자를 발송해야 한다 (숫자 섹션은 영향 없음).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, skipping comment")
        return None

    context_lines = []
    for name, result in snapshot.get("indices", {}).items():
        if result.get("ok"):
            direction = "상승" if result["change_pct"] > 0 else "하락" if result["change_pct"] < 0 else "보합"
            context_lines.append(f"- {name} {direction}")
    for rate_name, rate in snapshot.get("rates", {}).items():
        if rate.get("ok"):
            direction = "상승" if rate["change_bp"] > 0 else "하락" if rate["change_bp"] < 0 else "보합"
            context_lines.append(f"- {rate_name} 금리 {direction}")
    if news_headlines:
        context_lines.append("참고 뉴스 헤드라인: " + " / ".join(news_headlines))

    user_prompt = "오늘 시장 상황:\n" + "\n".join(context_lines) + "\n\n위 내용을 바탕으로 한 줄 코멘트를 작성하라."

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        comment = response.content[0].text.strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Claude comment generation failed: %s", exc)
        return None

    if not _comment_numbers_are_valid(comment, snapshot):
        logger.warning("discarding comment due to unverifiable numbers: %s", comment)
        return None

    return comment
