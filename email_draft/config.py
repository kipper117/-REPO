"""
설정값. 실제 개인정보(전화번호 등)는 .env로 관리하고, 여기엔 기본값/플레이스홀더만 둔다.
"""
import os

SENDER_TITLE = os.environ.get("EMAIL_SENDER_TITLE", "삼성증권 이동주PB")
SENDER_GREETING_LINE = os.environ.get(
    "EMAIL_SENDER_GREETING_LINE", "삼성증권 평촌지점 이동주 주임입니다."
)
OFFICE_PHONE = os.environ.get("EMAIL_OFFICE_PHONE", "031-000-0000")
MOBILE_PHONE = os.environ.get("EMAIL_MOBILE_PHONE", "010-0000-0000")

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")

# 리포트 폴더 이름 규칙: "YYMMDD_리포트" (바탕화면 등에 직접 만드는 걸 가정, 고정 위치 강제 안 함)
REPORT_FILENAME_SEP = "_"  # "{증권사}_{주제}_{제목}_{YYYYMMDD}.pdf" 패턴 파싱용

# 구글 시트 "Data" 탭 히스토리 읽기 (전주비 계산용, 선택 기능)
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_PATH = os.environ.get(
    "GOOGLE_SERVICE_ACCOUNT_PATH",
    os.path.join(os.path.dirname(__file__), "credentials", "service_account.json"),
)

# Gmail API: 초안(draft) 생성만 가능한 최소 권한 스코프
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
GMAIL_CLIENT_SECRET_PATH = os.environ.get(
    "GMAIL_CLIENT_SECRET_PATH", os.path.join(os.path.dirname(__file__), "credentials", "client_secret.json")
)
GMAIL_TOKEN_PATH = os.environ.get(
    "GMAIL_TOKEN_PATH", os.path.join(os.path.dirname(__file__), "credentials", "token.json")
)
