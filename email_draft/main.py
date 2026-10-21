"""
사용법:
    python -m email_draft.main "C:\\Users\\marti\\OneDrive\\바탕 화면\\261021_리포트"

흐름: 폴더의 PDF 리포트들 텍스트 추출 -> Claude로 요약부 생성 ->
      인사말/마무리/서명 붙여 완성 -> Gmail "초안"으로 저장 (발송 안 함).
"""
from __future__ import annotations

import logging
import sys

from . import composer, gmail_client, pdf_reader

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run(folder_path: str, to: str = "") -> None:
    logger.info("reading reports from %s", folder_path)
    reports = pdf_reader.load_reports(folder_path)
    if not reports:
        print(f"'{folder_path}' 안에 PDF 파일이 없습니다.")
        return

    ok_reports = [r for r in reports if r["text"].strip()]
    failed = [r for r in reports if not r["text"].strip()]
    print(f"리포트 {len(reports)}개 중 텍스트 추출 성공 {len(ok_reports)}개, 실패 {len(failed)}개")
    for r in failed:
        print(f"  - 추출 실패: {r['filename']}")

    logger.info("composing email with Claude...")
    result = composer.compose(reports)
    if not result.get("ok"):
        print(f"메일 생성 실패: {result.get('reason')}")
        return

    full = composer.build_full_email(result["subject"], result["body"])

    print("\n========== 미리보기 ==========")
    print(f"제목: {full['subject']}")
    print("-" * 40)
    print(full["body"])
    print("================================\n")

    logger.info("creating Gmail draft...")
    draft_result = gmail_client.create_draft(full["subject"], full["body"], to=to)
    if draft_result.get("ok"):
        print(f"Gmail 임시보관함에 초안을 저장했습니다 (draft_id={draft_result['draft_id']}).")
        print("Gmail을 열어 수신자/내용을 검수한 뒤 직접 발송해주세요.")
    else:
        print(f"Gmail 초안 저장 실패: {draft_result.get('reason')}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('사용법: python -m email_draft.main "<리포트 폴더 경로>" [받는사람 이메일]')
        sys.exit(1)
    folder = sys.argv[1]
    recipient = sys.argv[2] if len(sys.argv) > 2 else ""
    run(folder, recipient)
