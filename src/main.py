"""
전체 파이프라인:
1. snapshot 수집 + 저장
2. 기대 거래일과 실제 거래일 비교 (다르면 발송 중단 + 경고만 전송)
3. 문구 생성 (숫자: 템플릿 코드, 코멘트 1줄: Claude + 검증)
4. 텔레그램 발송 (본문 + 실패/이상치 경고 분리)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from . import claude_comment, snapshot as snapshot_mod, telegram_sender
from .formatters import bond_message, news_section, stock_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


def expected_trade_date(now_kst: datetime) -> str:
    """
    KST 기준 '오늘'로부터 가장 최근의 미국 영업일(주말 제외)을 기대 거래일로 계산.
    미국 공휴일은 고려하지 않는다 -> 공휴일이면 실제 데이터의 거래일과 어긋나고,
    main()이 그 차이를 감지해서 발송을 중단한다.
    """
    candidate = now_kst.date() - timedelta(days=1)
    while candidate.weekday() >= 5:  # 5=토, 6=일
        candidate -= timedelta(days=1)
    return candidate.strftime("%Y-%m-%d")


def run() -> None:
    now_kst = datetime.now(KST)

    logger.info("collecting snapshot...")
    snap = snapshot_mod.build_snapshot()
    snapshot_mod.save_snapshot(snap)

    if not snap.get("trade_date"):
        logger.error("no trade_date could be determined; aborting")
        telegram_sender.send_abort_notice("모든 데이터 소스 조회에 실패해 거래일을 확인할 수 없습니다.")
        return

    expected = expected_trade_date(now_kst)
    if snap["trade_date"] != expected:
        logger.error("trade_date mismatch: expected=%s actual=%s", expected, snap["trade_date"])
        telegram_sender.send_abort_notice(
            f"기대 거래일({expected})과 실제 데이터 거래일({snap['trade_date']})이 다릅니다. "
            f"휴장 등의 사유로 보이며 발송을 중단합니다."
        )
        return

    news = snap.get("news", {})
    headlines = news.get("headlines") if news.get("ok") else None
    comment = claude_comment.generate_one_line_comment(snap, headlines)

    # 전일 핵심 이슈: Claude로 한국어 요약 시도, 안 되면 원문 헤드라인으로 대체
    news_bullets = claude_comment.generate_top_news_bullets(headlines) if headlines else None
    if not news_bullets:
        news_bullets = headlines

    parts = []
    news_text = news_section.build_news_section(news_bullets)
    if news_text:
        parts.append(news_text)
    parts.append(stock_message.build_stock_section(snap))
    bond_section = bond_message.build_bond_section(snap)
    if bond_section:
        parts.append(bond_section)
    if comment:
        parts.append(f"> {comment}")

    telegram_sender.send_briefing("\n\n".join(parts))
    telegram_sender.send_warning(snap["failures"], snap["anomalies"])

    logger.info("done. failures=%d anomalies=%d", len(snap["failures"]), len(snap["anomalies"]))


if __name__ == "__main__":
    run()
