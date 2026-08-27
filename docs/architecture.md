# RFP Lens 아키텍처

## 데이터 흐름

```text
브라우저 (React/Vite SPA)
   │  Bearer JWT
   ▼
FastAPI (/api) ── SQLAlchemy ── PostgreSQL
   │                │
   │ 저장            └─ alembic 마이그레이션
   ▼
LocalFileStore (storage_root, 웹 루트 외부)
   │
   └─ process_document.delay() ── Redis 브로커 ── Celery worker
                                                     │ 1. 파싱 → DocumentBlockRecord
                                                     │ 2. 청킹 → provider.extract()
                                                     │ 3. 검증 → Evidence(verified)
                                                     │ 4. 요약 → AnalysisSummary(highlights)
                                                     ▼
                                              AnalysisJob / Requirement / Evidence
```

- **analysis 도메인은 원본 파일을 읽지 않습니다.** worker가 파싱해 만든 블록만 사용합니다.
- **overview 도메인은 검증된 요구사항과 근거만 요약 공급자에 전달합니다.** 통계는 DB에서 결정론적으로 계산하고 AI가 반환한 요구사항 ID/분류를 서버가 재검증합니다.
- **compliance 도메인은 확정/수정된 요구사항만 소비합니다.**

## 공통 블록 모델

PDF와 HWPX는 각기 다른 파서를 거치지만 동일한 `DocumentBlock` 계약으로 수렴합니다.

| 필드 | 설명 |
| --- | --- |
| `block_id` | `pdf-p{page}-b{i}` / `hwpx-{section}-p{i}` 형식 |
| `order` | 문서 순서 (청킹과 DB 정렬의 기준) |
| `kind` | heading / paragraph / table |
| `text` | 정규화된 텍스트 (표는 탭/개행 구분 셀 직렬화) |
| `heading_path` | 조상 제목 목록 — LLM 프롬프트의 맥락 |
| `locator` | 원문 위치 (아래 표) |
| `metadata` | 포맷별 부가 정보 |

### PDF/HWPX locator 차이

| | PDF | HWPX |
| --- | --- | --- |
| 위치 근거 | 물리 페이지 번호 + bbox | OPF spine 순서의 섹션 XML + 문단/표/행/열 인덱스 |
| 예시 표시 | `PDF p.12` | `HWPX Contents/section0.xml · 문단 8 · 표 2행 1열` |

PDF는 페이지라는 절대 좌표가 있고 HWPX는 문서 구조 좌표만 있습니다. UI는 두 locator 모두 **원문 페이지 번호를 추측하지 않고** 그대로 표시합니다.

## 워커 상태 머신

```text
UPLOADED ──분석 시작──▶ PARSING ──블록 저장 성공──▶ ANALYZING ──▶ REVIEW_REQUIRED
   │                       │                          │              PARTIAL
   │                       ├─ 스캔 PDF ▶ OCR_REQUIRED  └─ 전 청크 실패 ▶ FAILED
   │                       └─ 파싱 오류 ▶ FAILED
   └── 삭제
```

- `process_document`는 `SELECT ... FOR UPDATE`로 문서 행을 잠그고, 재시도 시 현재 시도의 블록만 교체해 멱등성을 보장합니다.
- `run_analysis`는 청크 단위로 실패를 누적합니다: 일부 실패면 `PARTIAL`, 전부 실패면 `FAILED`.
- 분석은 새 `AnalysisJob` 하위로 pending 요구사항을 삽입하며, 사용자가 `CONFIRMED/REJECTED/EDITED` 상태로 만든 요구사항은 재분석에도 덮어쓰지 않습니다.

## 제공자 경계 (provider boundary)

```python
class RequirementProvider(Protocol):
    def extract(self, chunks: list[AnalysisChunk]) -> tuple[list[ExtractedRequirement], ExtractionUsage]: ...
```

- 요구사항 추출 구현체는 `OpenAIRequirementProvider`(Responses structured outputs, `store=False`, 60s timeout), `LocalRequirementProvider`(OpenAI 호환 JSON schema, 300s timeout), `FakeRequirementProvider`입니다.
- 최종 요약은 별도 `SummaryProvider` 경계와 같은 OpenAI/local/fake 선택을 사용하며 `(project_id, scope)`별로 저장됩니다. fingerprint가 바뀌면 이전 성공 결과를 유지한 채 Celery가 갱신합니다.
- 팩터리(`create_requirement_provider`)는 `fake`를 test/demo 환경에서만 허용하고, `openai`는 API 키를 요구합니다.
- 청킹은 결정론적입니다(블록 분할 없음, 대상 4,000자, 2블록 overlap, 표는 원자적).
- 로그에는 입력/출력 텍스트, 프롬프트, 키를 남기지 않습니다. 사용량(latency/token)만 기록합니다.

## 근거 검증 신뢰 경계

1. LLM은 각 요구사항마다 `source_block_id`와 verbatim 인용을 반드시 반환합니다.
2. 서버는 인용을 NFKC + 공백 정규화한 뒤 해당 블록 텍스트에 포함되는지 **결정론적으로** 대조해 `Evidence.verified`를 설정합니다.
3. `verified=False`인 요구사항은 UI 확인 대화상자와 `confirm_unverified=true` API 플래그 없이는 확정할 수 없습니다.
4. 즉, **AI 출력이 사실로 승격되는 유일한 경로는 사람의 검토이며**, 자동 검증은 "인용이 원문에 존재한다"는 최소 보장만 제공합니다.

## 배포 토폴로지 (compose.yaml)

| 서비스 | 이미지 | 비고 |
| --- | --- | --- |
| postgres | postgres:16-alpine | 헬스체크 `pg_isready` |
| redis | redis:7-alpine | Celery 브로커/리절트 백엔드 |
| api | backend (Python 3.12 slim + uv) | 기동 시 `alembic upgrade head` → uvicorn, 비루트 사용자 |
| worker | api와 동일 이미지 | celery prefork, storage 볼륨 공유 |
| web | frontend (Node 22 빌드 → nginx) | `/api`를 api 서비스로 프록시, SPA fallback |

모든 서비스는 healthcheck를 가지며 의존성은 `service_healthy` 조건으로 선언됩니다.
