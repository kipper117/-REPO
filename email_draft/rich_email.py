"""
"풍성한" 고객 메일 = 인사말 + 상단 하이라이트 박스 + 시황 서술(섹션별) +
리포트 요약(선택, PDF 폴더 기반) + 주요 헤드라인 뉴스(선택) + HTML 대시보드 표 + 마무리/서명.

이 모듈은 조립만 한다 — 실제 "요약 문장"은 호출부(Claude Code 세션, 즉 지금 이 대화)가
pdf_reader.load_reports()로 읽은 리포트 원문과 snapshot 데이터를 보고 직접 작성해서
섹션 리스트로 넘겨준다. (ANTHROPIC_API_KEY 없이도 쓸 수 있는 "무료" 경로와 동일한 원칙:
숫자/사실은 코드·데이터가, 문장은 Claude가, 인사말/서명은 코드가 고정값으로.)

사용 예:
    sections = [("美 증시 (10/20 마감)", "..."), ...]          # 시황 서술
    report_sections = [("KB증권 - ...", "..."), ...]           # (선택) 리포트 요약
    headlines = [("번역된 헤드라인", "로이터"), ...]            # (선택)

    built = rich_email.build(
        subject="...", sections=sections, snapshot=snap, history=history,
        report_sections=report_sections, headlines=headlines,
    )
    gmail_client.create_draft(built["subject"], built["plain"], html_body=built["html"])
"""
from __future__ import annotations

from . import composer, html_dashboard


def _html_sections(sections: list[tuple[str, str]]) -> str:
    return "".join(
        f'<h3 style="font-family:Arial,sans-serif;font-size:14px;margin:16px 0 4px 0;">{title}</h3>'
        f'<p style="font-family:Arial,sans-serif;font-size:13px;line-height:1.6;margin:0 0 8px 0;">{body}</p>'
        for title, body in sections
    )


def _plain_headlines(headlines: list[tuple[str, str]]) -> str:
    if not headlines:
        return ""
    lines = ["■ 주요 헤드라인 뉴스"]
    lines.extend(f"- {text} ({source})" for text, source in headlines)
    return "\n".join(lines)


def _html_headlines(headlines: list[tuple[str, str]]) -> str:
    if not headlines:
        return ""
    items = "".join(f'<li>{text} <span style="color:#888;">({source})</span></li>' for text, source in headlines)
    return (
        '<h3 style="font-family:Arial,sans-serif;font-size:14px;margin:16px 0 4px 0;">주요 헤드라인 뉴스</h3>'
        f'<ul style="font-family:Arial,sans-serif;font-size:13px;line-height:1.7;margin:0 0 8px 0;padding-left:18px;">{items}</ul>'
    )


def build(
    subject: str,
    intro: str,
    sections: list[tuple[str, str]],
    snapshot: dict,
    history: dict | None = None,
    report_sections: list[tuple[str, str]] | None = None,
    headlines: list[tuple[str, str]] | None = None,
) -> dict:
    """
    subject: 메일 제목
    intro: 본문 맨 앞 한 줄 소개 (예: "오늘(10/21) 국내외 증시 동향을 정리해 보내드립니다.")
    sections: [(소제목, 본문), ...] — 시황 서술 (숫자는 snapshot 기준으로 직접 작성)
    report_sections: [(소제목, 본문), ...] — 리포트 폴더 요약 (있으면 표 아래에 추가)
    headlines: [(번역/원문 헤드라인, 출처), ...]
    """
    report_sections = report_sections or []
    headlines = headlines or []

    # ---- plain text ----
    plain_parts = [intro, ""]
    for title, body in sections:
        plain_parts.append(f"■ {title}\n{body}\n")
    if report_sections:
        plain_parts.append("■ 관련 리포트 요약")
        for title, body in report_sections:
            plain_parts.append(f"▸ {title}\n{body}\n")
    headline_plain = _plain_headlines(headlines)
    if headline_plain:
        plain_parts.append(headline_plain)
    plain_parts.append("\n[상세 수치는 함께 첨부된 표를 참고해주세요.]")
    summary_body = "\n".join(p for p in plain_parts if p)

    full = composer.build_full_email(subject, summary_body)

    # ---- html ----
    highlight_html = html_dashboard.build_highlight_bar(snapshot)
    dashboard_html = html_dashboard.build_dashboard_html(snapshot, history=history)

    report_html = ""
    if report_sections:
        report_html = (
            '<h3 style="font-family:Arial,sans-serif;font-size:15px;margin:20px 0 4px 0;'
            'border-top:1px solid #d9d3c4;padding-top:12px;">관련 리포트 요약</h3>'
            + _html_sections(report_sections)
        )

    html_body = (
        '<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;">'
        f"<p>안녕하십니까,<br>{composer.config.SENDER_GREETING_LINE}</p>"
        f"{highlight_html}"
        f"<p>{intro}</p>"
        f"{_html_sections(sections)}"
        f"{report_html}"
        f"{_html_headlines(headlines)}"
        f"{dashboard_html}"
        '<p style="margin-top:18px;">추후 또 업데이트 드리겠습니다.<br>감사합니다.</p>'
        f'<p style="color:#555;">{composer.config.SENDER_TITLE}<br>'
        f"{composer.config.OFFICE_PHONE}<br>{composer.config.MOBILE_PHONE}</p>"
        "</div>"
    )

    return {"subject": full["subject"], "plain": full["body"], "html": html_body}
