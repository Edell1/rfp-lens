# RFP Lens

정부 R&D 공고문(PDF/HWPX)을 업로드하면 AI가 **원문 근거가 연결된 요구사항**을 추출하고, 사람의 검토를 거쳐 **컴플라이언스 매트릭스(XLSX)** 로 내보내 주는 웹 애플리케이션입니다.

## 해결하는 문제

제안 담당자는 수십 페이지 공고문에서 지원 자격, 예산 한도, 일정 같은 요구사항을 수작업으로 찾아 표로 정리합니다. 이 과정은 느리고, 근거 없는 요약이 생기기 쉽습니다. RFP Lens는 모든 추출 결과에 **원문 인용(evidence quote)** 과 위치(locator)를 강제로 붙여, 검증되지 않은 근거는 자동 확정될 수 없도록 만듭니다.

## 주요 기능

- 회원가입/로그인, 소유권 기반 프로젝트 관리
- PDF·HWPX 안전 업로드 (25MiB 제한, ZIP 폭탄/경로 탐색/XML 엔티티 차단)
- Celery 비동기 파이프라인: 파싱 → 청킹 → 구조화된 요구사항 추출
- OpenAI 호환 structured outputs + 결정론적 원문 인용 검증
- 요구사항 확정/수정/제외, 컴플라이언스 매트릭스, XLSX 내보내기(수식 인젝션 방어)

## 아키텍처

상세 설계는 [docs/architecture.md](docs/architecture.md), 2분 데모 시나리오는 [docs/demo-script.md](docs/demo-script.md)를 참고하세요.

```text
React SPA ── FastAPI ── PostgreSQL
                │              ▲
                ├── Redis ── Celery worker
                │               └── PDF/HWPX 파서 → 블록 저장 → LLM 추출 → 근거 검증
                └── 로컬 파일 스토리지 (웹 루트 외부)
```

## 빠른 시작 (Docker Compose)

```bash
docker compose up --build -d          # postgres, redis, api, worker, web
curl http://localhost:8080/api/health  # {"status":"ok"}
```

브라우저에서 http://localhost:8080 접속.

**네트워크 호출 없이 체험**(합성 fake provider):

```bash
cp .env.example .env
# .env에서 두 값을 변경:
#   RFP_LENS_ENVIRONMENT=demo
#   RFP_LENS_AI_PROVIDER=fake
docker compose up --build -d
```

demo 환경의 fake provider는 커밋된 합성 문구("중소기업만 신청 가능", "정부출연금은 총 5억원 이내이다.")만 인식합니다. [docs/demo-script.md](docs/demo-script.md)의 합성 HWPX를 올려 보세요.

**로컬 모델로 분석**(Ollama 예시):

```bash
ollama pull qwen2.5:7b && ollama serve
# .env 설정:
#   RFP_LENS_AI_PROVIDER=local
#   RFP_LENS_LOCAL_BASE_URL=http://host.docker.internal:11434/v1   (컨테이너 → 호스트)
#   RFP_LENS_LOCAL_MODEL=qwen2.5:7b
docker compose up -d
cd backend && uv run python -m evals.run --provider local --cases-dir evals/cases   # 근거 검증률 측정
```

소형 로컬 모델은 원문 verbatim 인용 실패가 잦으므로 `evidence_verification_rate`를 먼저 확인하세요.

## 로컬 개발

요구 사항: Python 3.12+, Node 22+, Docker(PostgreSQL 16/Redis 7).

```bash
docker compose up -d postgres redis
cp .env.example backend/.env

cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --port 8000
cd frontend && npm install && npm run dev        # http://localhost:5173
```

## 테스트 · 평가 · E2E

```bash
cd backend && uv run pytest -q                                   # 백엔드 전체
cd backend && uv run alembic check                               # 마이그레이션-모델 일치
cd frontend && npm test -- --run && npm run build                # 프런트엔드
cd backend && uv run python -m evals.run --provider fake --output eval-results.json
cd e2e && npm install && npx playwright install chromium && npm test   # 브라우저 E2E
```

## 평가 지표 정의 (`evals/run.py` 출력)

| 지표 | 정의 |
| --- | --- |
| `precision` | 추출된 요구사항 중 기대 집합과 일치하는 비율 (오탐 감점) |
| `recall` | 기대 요구사항 중 추출된 비율 (누락 감점) |
| `evidence_verification_rate` | 모든 근거 인용 중 원문 대조를 통과한 비율 |
| `latency_ms` / `input_tokens` / `output_tokens` | 제공자 사용량 누계 |
| `estimated_cost` | 명시적 단가표(MODEL_PRICES)로 계산한 USD 추정액 |

일치 판정은 NFKC 정규화 + 문장부호/공백 제거 후 비교합니다.

## 환경변수 (`RFP_LENS_` 접두사)

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `DATABASE_URL` | 로컬 PostgreSQL DSN | SQLAlchemy 접속 문자열 |
| `REDIS_URL` | redis://localhost:6379/0 | Celery 브로커/백엔드 |
| `STORAGE_ROOT` | `storage` | 업로드 파일 저장 루트 |
| `JWT_SECRET` | `change-me` | test 외 환경에서 기본값 사용 시 기동 거부 |
| `ENVIRONMENT` | development | development/test/demo/production |
| `AI_PROVIDER` | openai | openai / fake(test·demo 전용) / local(자체 호스팅) |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | -, gpt-5-mini | 클라우드 추출 설정 |
| `LOCAL_BASE_URL`, `LOCAL_MODEL` | http://localhost:11434/v1, - | Ollama·vLLM·LM Studio 등 OpenAI 호환 로컬 서버. Docker 실행 시 `host.docker.internal` 사용(예: LM Studio `http://host.docker.internal:1234/v1`) |
| `MAX_UPLOAD_BYTES` | 26214400 | 25 MiB |
| `CELERY_TASK_ALWAYS_EAGER` | false | E2E/테스트용 동기 실행 |

## 스크린샷/GIF 캡처 명령

```bash
# 화면 녹화(GIF): ffmpeg 예시 — 1280x800 영역을 12fps로 캡처
ffmpeg -f gdigrab -framerate 12 -offset_x 100 -offset_y 100 -video_size 1280x800 \
       -i : -t 120 -vf "fps=12,scale=960:-1:flags=lanczos" docs/demo.gif
```

macOS/Linux는 `-f gdigrab` 대신 `-f avfoundation`/`-f x11grab`을 사용하세요.

## 보안 모델

- 업로드는 시그니처 기반으로 형식 판별하며 ZIP 멤버 수(≤500), 전개 크기(≤100MiB), 압축비(≤100:1), 경로 탐색, XML 외부 엔티티를 거부합니다.
- 저장 경로는 원본 파일명을 사용하지 않습니다.
- 모든 AI 요구사항은 원문 블록 ID + verbatim 인용을 요구하며, 서버가 NFKC/공백 정규화 후 대조해 `verified`를 판정합니다. 미검증 근거는 `confirm_unverified=true` 없이 확정할 수 없습니다.
- XLSX 내보내기는 `=`, `+`, `-`, `@`로 시작하는 값을 apostrophe로 이스케이프합니다.
- 타인의 리소스 접근은 존재 여부 노출을 피하기 위해 404로 응답합니다.
- 회귀 방지 테스트: `backend/tests/integration/test_security_boundaries.py`

> **클라우드 데이터 경고**: `AI_PROVIDER=openai`일 때 공고문에서 파싱된 텍스트(블록 단위)가 OpenAI API로 전송됩니다. 회사 기밀 문서를 올리지 마세요. MVP는 공개 공고문 또는 합성 데이터만 가정합니다.

## 명시적 제외 (MVP 범위 밖)

- 구형 HWP(바이너리 OLE) 형식
- OCR 실행 (스캔 PDF는 `ocr_required` 상태로 안내만 제공)
- 암호화된 문서, 벡터 검색, 제안서 생성, 실시간 협업
