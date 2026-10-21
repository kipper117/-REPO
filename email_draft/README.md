# email_draft — 리포트 폴더 → 고객 메일 초안 (1단계: 텍스트만)

특정 폴더에 넣어둔 증권사 리포트 PDF들을 읽어 Claude로 요약하고,
**Gmail 임시보관함에 "초안"으로만** 저장한다. 자동 발송은 하지 않는다 —
Gmail을 열어 수신자 지정 + 내용 검수 후 직접 발송하는 흐름을 전제로 한다.

이 봇(`src/`, GitHub Actions)과는 별개로 **본인 PC에서 직접 실행**한다
(로컬 폴더를 읽어야 하므로 클라우드에서는 돌릴 수 없다).

## 1단계 범위

- 입력: PDF 리포트 (텍스트 추출 가능한 것 — 스캔 이미지 PDF는 지원 안 함)
- 출력: 텍스트 중심 메일 초안. **이미지(차트 등)는 아직 안 들어간다** — 검수 시 직접 추가.
- 나중 단계에서 "PDF 안에 이미 있는 차트 이미지를 추출해 재사용" 추가 예정.

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
