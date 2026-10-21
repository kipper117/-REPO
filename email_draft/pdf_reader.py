"""폴더 안 PDF 리포트들의 텍스트를 추출한다."""
from __future__ import annotations

import logging
import os

import pdfplumber

from . import config

logger = logging.getLogger(__name__)


def _parse_source_and_title(filename: str) -> tuple[str, str]:
    """
    "KB증권_스페이스X_[AI 실적속보] FY26 3분기 실적 및 가이던스 리뷰_20261021.pdf"
    -> ("KB증권", "스페이스X - [AI 실적속보] FY26 3분기 실적 및 가이던스 리뷰")
    패턴이 안 맞으면 (파일명, 파일명)을 반환한다.
    """
    name = os.path.splitext(filename)[0]
    parts = name.split(config.REPORT_FILENAME_SEP)
    if len(parts) < 2:
        return name, name
    source = parts[0]
    # 마지막 조각이 YYYYMMDD 형태의 날짜면 제목에서 제외한다.
    body_parts = parts[1:]
    if body_parts and body_parts[-1].isdigit() and len(body_parts[-1]) == 8:
        body_parts = body_parts[:-1]
    title = " - ".join(p for p in body_parts if p)
    return source, title or name


def extract_text(pdf_path: str) -> str:
    """PDF 전체 페이지의 텍스트를 이어 붙여 반환. 실패하면 빈 문자열."""
    try:
        chunks = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text.strip():
                    chunks.append(text)
        return "\n".join(chunks)
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed to extract text from %s: %s", pdf_path, exc)
        return ""


def load_reports(folder_path: str) -> list[dict]:
    """
    폴더 안의 PDF들을 읽어 리스트로 반환한다.
    각 항목: {"filename":, "source": 증권사, "title": 리포트 제목, "text": 추출된 본문}
    텍스트 추출에 실패한 파일은 "text"가 빈 문자열로 들어가며 호출부가 걸러낼 수 있다.
    """
    if not os.path.isdir(folder_path):
        raise FileNotFoundError(f"폴더를 찾을 수 없습니다: {folder_path}")

    reports = []
    for filename in sorted(os.listdir(folder_path)):
        if not filename.lower().endswith(".pdf"):
            continue
        source, title = _parse_source_and_title(filename)
        text = extract_text(os.path.join(folder_path, filename))
        reports.append({"filename": filename, "source": source, "title": title, "text": text})
    return reports
