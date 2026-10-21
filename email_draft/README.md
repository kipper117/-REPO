# email_draft — 리포트 폴더 → 고객 메일 초안 (1단계: 텍스트만)

특정 폴더에 넣어둔 증권사 리포트 PDF들을 읽어 Claude로 요약하고,
**Gmail 임시보관함에 "초안"으로만** 저장한다. 자동 발송은 하지 않는다 —
Gmail을 열어 수신자 지정 + 내용 검수 후 직접 발송하는 흐름을 전제로 한다.

이 봇(`src/`, GitHub Actions)과는 별개로 **본인 PC에서 직접 실행**한다
(로컬 폴더를 읽어야 하므로 클라우드에서는 돌릴 수 없다).

## 범위

- 입력: PDF 리포트 (텍스트 추출 가능한 것 — 스캔 이미지 PDF는 지원 안 함) 또는
  시황봇(`src/`)이 모으는 지수/환율/금리/종목 데이터
- 출력: 서사형 텍스트 요약 + **HTML 대시보드 표**(상승=빨강/하락=파랑) + 상단 하이라이트 박스 +
  신뢰도 높은 최신 헤드라인 뉴스(번역 확신 없으면 원문 유지/제외)
- 실제 Claude 호출 없이도(=무료) 동작 가능: Claude Code 세션 안에서 직접 요약문을
  만들고 `gmail_client.create_draft()`를 호출하는 방식. `composer.compose()`는
  완전 자동화(무인 실행)가 필요해질 때를 위한 선택 경로.
- 나중 단계: "PDF 안에 이미 있는 차트 이미지를 추출해 재사용" (아직 미구현)

## HTML 대시보드 표 + 전주비

`email_draft/html_dashboard.py`가 표/하이라이트 박스를 만든다. `history` 인자로
구글 시트 "Data" 탭의 과거 기록을 넘기면 "전주비" 열도 추가된다 (안 넘기면 당일비만).

히스토리를 읽으려면 시황봇과 같은 구글 서비스 계정 키가 로컬에도 필요하다:
- `email_draft/credentials/service_account.json`에 저장 (GitHub Secrets에 등록한 것과 동일한 JSON)
- 환경변수 `GOOGLE_SHEET_ID` 필요 (구글 시트 URL의 `/d/`와 `/edit` 사이 문자열)

```python
from email_draft import sheet_history
history = sheet_history.load_history()  # 설정 안 돼 있으면 빈 dict (전주비만 생략됨)
```

데이터가 일주일 미만이면 전주비 칸은 자연스럽게 빈 칸("-")으로 나온다.

## 합쳐서 "풍성한" 메일 만들기 (시황 + 리포트 요약)

평소처럼 Claude Code 세션(지금 이 대화)에서:
1. "이 폴더(예: `261021_리포트`)랑 오늘 시황 데이터 합쳐서 메일 만들어줘" 라고 요청
2. `pdf_reader.load_reports()`로 리포트 읽고, `src.snapshot.build_snapshot()`로 시황 데이터 수집
3. Claude(지금 이 세션)가 시황 서술 + 리포트별 요약 문장을 작성
4. `email_draft/rich_email.py`의 `build()`로 한 번에 조립:

```python
from email_draft import rich_email, sheet_history, gmail_client

built = rich_email.build(
    subject="(삼성증권 이동주PB) 10/21 시황 브리핑",
    intro="오늘 국내외 증시 동향과 함께 받은 리포트를 정리해 보내드립니다.",
    sections=[("美 증시 (...)", "..."), ...],          # 시황 서술
    snapshot=snap,                                      # src.snapshot.build_snapshot() 결과
    history=sheet_history.load_history(),                # 선택: 전주비
    report_sections=[("KB증권 - ...", "..."), ...],      # 선택: 리포트 요약
    headlines=[("번역된 헤드라인", "로이터"), ...],       # 선택
)
gmail_client.create_draft(built["subject"], built["plain"], html_body=built["html"])
```

리포트 요약은 "관련 리포트 요약" 섹션으로 대시보드 표 바로 위에 들어간다.
리포트 폴더 없이 시황 데이터만으로도(`report_sections` 생략) 그대로 동작한다.

## 최초 1회 설정

### 1) 패키지 설치

```bash
pip install -r email_draft/requirements.txt
```

### 2) Claude API 키

repo 루트의 `.env`(또는 환경변수)에 `ANTHROPIC_API_KEY`가 있으면 그대로 쓴다.

### 3) Gmail OAuth 클라이언트 (최초 1회)

1. https://console.cloud.google.com/ → (기존 프로젝트 재사용 가능) → **API 및 서비스 → 라이브러리**
   → `Gmail API` 검색 → 사용
2. **API 및 서비스 → 사용자 인증 정보 → + 사용자 인증 정보 만들기 → OAuth 클라이언트 ID**
   - 애플리케이션 유형: **데스크톱 앱**
   - (OAuth 동의 화면을 먼저 설정하라고 하면 "외부" + 본인 이메일만 테스트 사용자로 추가하면 됨)
3. 다운로드한 JSON을 `email_draft/credentials/client_secret.json`으로 저장
   (이 폴더는 `.gitignore`에 들어있어 절대 커밋되지 않는다)
4. 처음 실행하면 브라우저가 열리며 본인 Gmail 계정으로 로그인 + 동의 — 이후엔
   `email_draft/credentials/token.json`에 저장되어 자동 재사용된다.

### 4) (선택) 서명 커스터마이즈

`.env`에 아래 값을 넣으면 기본값 대신 사용된다:

```
EMAIL_SENDER_TITLE=삼성증권 이동주PB
EMAIL_SENDER_GREETING_LINE=삼성증권 평촌지점 이동주 주임입니다.
EMAIL_OFFICE_PHONE=031-000-0000
EMAIL_MOBILE_PHONE=010-0000-0000
```

## 실행

```bash
python -m email_draft.main "C:\Users\marti\OneDrive\바탕 화면\261021_리포트"
```

실행하면:
1. 폴더 안 PDF들의 텍스트를 추출
2. Claude가 리포트별 핵심 요약 + 출처 증권사를 명시한 본문을 작성
   (리포트에 없는 숫자/사실은 지어내지 않도록, 투자 권유 문구를 새로 추가하지 않도록 프롬프트에서 제한)
3. 인사말/마무리/서명은 Claude가 아니라 코드가 고정값으로 붙인다 (연락처 오기재 방지)
4. 터미널에 미리보기 출력 후, Gmail 임시보관함에 초안 저장

받는사람을 미리 지정하고 싶으면 두 번째 인자로 넘기면 된다:

```bash
python -m email_draft.main "C:\...\261021_리포트" "client@example.com"
```
