"""'전일 핵심 이슈' 섹션. 숫자가 들어간 시세 섹션들보다 먼저 보여준다."""
from __future__ import annotations


def build_news_section(bullets: list[str] | None, max_items: int = 5) -> str | None:
    """
    bullets: 이미 정리된 한국어(혹은 원문) 한 줄 요약 리스트.
    비어 있으면 None -> 호출부가 섹션을 통째로 생략한다.
    """
    if not bullets:
        return None

    lines = ["[전일 핵심 이슈]"]
    for i, bullet in enumerate(bullets[:max_items], start=1):
        lines.append(f"{i}. {bullet}")
    return "\n".join(lines)
