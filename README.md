# -REPO — 美 증시/채권 일일 시황 봇

매일 평일 07:00(KST)에 美 증시/채권 시황 요약을 생성해 텔레그램으로 발송하는 봇.
GitHub Actions 스케줄로 실행되며, 수동 실행(`workflow_dispatch`)도 가능하다.

## 동작 흐름

1. `src/snapshot.py` — yfinance(지수/종목), FRED(금리), Finnhub(뉴스)에서 데이터를 모아
   `snapshot.json`으로 저장하고 결측/이상치(±10% 종목, ±15bp 금리)를 검사한다.
2. `src/main.py` — snapshot의 거래일이 기대 거래일(직전 영업일)과 다르면
   휴장 등으로 판단해 **발송을 중단**하고 경고만 보낸다.
3. `src/formatters/*` — 숫자가 들어간 문장은 전부 코드가 생성한다(강세/약세 라벨 포함).
4. `src/claude_comment.py` — Claude가 숫자 없는 한 줄 코멘트만 생성하고,
   혹시 숫자가 섞여 나오면 snapshot 값과 대조해 불일치 시 코멘트를 버린다.
   매수/매도 권유, 단정적 전망 표현은 프롬프트에서 금지한다.
5. `src/telegram_sender.py` — 본문(주식/채권 각각)과 실패/이상치 경고를 분리해서 발송한다.

## 환경변수 (GitHub Secrets 또는 로컬 `.env`)

`.env.example` 참고. 코드에 직접 키/전화번호를 쓰지 않는다.

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `FRED_API_KEY`
- `FINNHUB_API_KEY`
- `ANTHROPIC_API_KEY` (선택: `CLAUDE_MODEL`)

## 로컬 실행

```bash
pip install -r requirements.txt
cp .env.example .env   # 값 채운 뒤
python -m src.main
```

## 테스트 (네트워크 불필요)

```bash
python tests/test_formatters.py
```

## 설정 변경

- 대상 종목/지표, 임계값: `src/config.py`
- 시가총액 상위 20개 목록은 수시로 바뀌므로 분기 1회 점검 권장.
