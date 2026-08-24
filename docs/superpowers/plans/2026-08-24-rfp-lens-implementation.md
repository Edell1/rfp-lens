# RFP Lens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a multi-user application that parses public PDF/HWPX government R&D RFPs, extracts evidence-linked requirements with a cloud LLM, and exports a human-reviewed compliance matrix.

**Architecture:** A React SPA calls a FastAPI API backed by PostgreSQL. Uploaded files are stored outside the web root; Celery workers parse them into a shared block model and run provider-neutral structured extraction. Redis carries jobs, while deterministic server-side validation verifies every evidence quote before results enter the review workflow.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, Celery, Redis 7, PostgreSQL 16, PyMuPDF, defusedxml, OpenAI-compatible structured outputs, openpyxl, React, TypeScript, Vite, TanStack Query, pytest, Vitest, Testing Library, Playwright, Docker Compose

**Spec:** `docs/superpowers/specs/2026-08-24-rfp-lens-design.md`

## Global Constraints

- Python 3.12 or newer; Node.js 22 or newer; PostgreSQL 16 or newer; Redis 7 or newer.
- FastAPI is the only HTTP backend and React/TypeScript/Vite is the only browser client.
- PDF and HWPX are equal first-class formats; legacy HWP, OCR execution, encrypted documents, vector search, proposal generation, and real-time collaboration are outside the MVP.
- External AI calls may receive only public or synthetic normalized text, never company-confidential files or text.
- Every AI requirement must name a source block and include a verbatim evidence quote; unverified evidence cannot be confirmed automatically.
- User edits survive re-analysis and ownership is checked on every project-scoped operation.
- File limits: 25 MiB upload, 500 ZIP members, 100 MiB expanded HWPX size, and 100:1 maximum compression ratio.
- Persist no complete document text, prompt, response, password, access token, or API key in application logs.

## Delivery map

- Week 1: Tasks 1-4 — repository, persistence, authentication, projects, and secure upload.
- Week 2: Tasks 5-9 — common parsing model, PDF/HWPX adapters, workers, structured AI extraction, and evidence validation.
- Week 3: Tasks 10-12 — compliance APIs, exports, and the complete browser workflow.
- Week 4: Tasks 13-14 — evaluation, end-to-end/security coverage, containers, CI, deployment documentation, and demo evidence.

## Planned file structure

```text
.
├── .env.example
├── .gitignore
├── compose.yaml
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/{config.py,db.py,celery_app.py,errors.py,logging.py}
│   │   ├── db/models.py
│   │   ├── auth/{schemas.py,service.py,dependencies.py,router.py}
│   │   ├── projects/{schemas.py,service.py,router.py}
│   │   ├── documents/{schemas.py,storage.py,validation.py,service.py,router.py,tasks.py}
│   │   ├── parsing/{types.py,registry.py,safety.py,pdf.py,hwpx.py}
│   │   ├── analysis/{types.py,chunking.py,provider.py,openai_provider.py,fake_provider.py,prompt.py,validator.py,service.py,tasks.py}
│   │   └── compliance/{schemas.py,service.py,router.py,export.py}
│   ├── tests/{unit,integration,fixtures}/
│   └── evals/{cases,run.py,metrics.py}
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── app/{router.tsx,query-client.ts,api.ts}
│   │   ├── features/auth/
│   │   ├── features/projects/
│   │   ├── features/documents/
│   │   ├── features/requirements/
│   │   └── features/compliance/
│   └── tests/
└── e2e/{rfp-lens.spec.ts,playwright.config.ts}
```

The backend is split by domain workflow. `parsing` is format-neutral at its public boundary, `analysis` cannot read original files, and `compliance` only consumes persisted verified/reviewed requirements.

---

### Task 1: Runnable repository and health checks

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `compose.yaml`
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/db.py`
- Create: `backend/tests/test_health.py`

**Interfaces:**
- Produces: `app.main.create_app() -> FastAPI`, `GET /api/health -> {"status":"ok"}`.
- Produces: `app.core.config.Settings` loaded from environment with test overrides.

- [ ] **Step 1: Write the failing health test**

```python
from fastapi.testclient import TestClient
from app.main import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the test and verify the package does not exist**

Run: `cd backend && uv run pytest tests/test_health.py -v`

Expected: FAIL during import because `app.main` has not been created.

- [ ] **Step 3: Create backend dependencies and configuration**

Define `backend/pyproject.toml` with Python `>=3.12` and runtime dependencies `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `sqlalchemy`, `alembic`, `psycopg[binary]`, `celery[redis]`, `pyjwt`, `pwdlib[argon2]`, `python-multipart`, `pymupdf`, `defusedxml`, `openai`, and `openpyxl`. Add test dependencies `pytest`, `pytest-asyncio`, `httpx`, `testcontainers[postgres,redis]`, and `freezegun`.

Implement the application factory:

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="RFP Lens", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

Set `Settings.database_url`, `redis_url`, `storage_root`, `jwt_secret`, `openai_api_key`, `openai_model`, `max_upload_bytes=26_214_400`, and `environment`. Fail startup outside tests when `jwt_secret` is unchanged.

- [ ] **Step 4: Add local services and ignored paths**

Create `compose.yaml` services named `postgres` and `redis` using PostgreSQL 16 and Redis 7, with health checks and named volumes. Put exact matching local URLs in `.env.example`. Ignore `.env`, `.venv`, `__pycache__`, `.pytest_cache`, `node_modules`, `dist`, `playwright-report`, `storage`, and `.superpowers`.

- [ ] **Step 5: Run the health test and service health checks**

Run: `cd backend && uv sync && uv run pytest tests/test_health.py -v`

Expected: PASS.

Run: `docker compose up -d postgres redis && docker compose ps`

Expected: both services become healthy.

- [ ] **Step 6: Commit the runnable foundation**

```bash
git add .gitignore .env.example compose.yaml backend
git commit -m "chore: initialize rfp lens backend"
```

---

### Task 2: Database schema and migrations

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/models.py`
- Modify: `backend/app/core/db.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_initial_schema.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/integration/test_models.py`

**Interfaces:**
- Produces: UUID SQLAlchemy models `User`, `Project`, `Document`, `DocumentBlockRecord`, `AnalysisJob`, `Requirement`, `Evidence`, and `ComplianceItem`.
- Produces: `get_db() -> Iterator[Session]` and `session_factory`.
- Produces enums `DocumentState`, `JobState`, `ReviewState`, `RequirementCategory`, `Importance`, and `ComplianceStatus`.

- [ ] **Step 1: Write model relationship tests**

```python
def test_project_delete_cascades_documents(db_session, user_factory) -> None:
    user = user_factory(email="owner@example.com")
    project = Project(owner_id=user.id, name="2027 공개 RFP")
    document = Document(
        project=project,
        original_name="rfp.hwpx",
        media_type="application/hwp+zip",
        checksum_sha256="a" * 64,
        storage_key="owner/project/document.hwpx",
        state=DocumentState.UPLOADED,
    )
    db_session.add(project)
    db_session.commit()
    db_session.delete(project)
    db_session.commit()
    assert db_session.get(Document, document.id) is None
```

Add a second test proving `User.email` is unique and a third proving `ComplianceItem.requirement_id` is unique.

- [ ] **Step 2: Run the model tests and verify missing model imports**

Run: `cd backend && uv run pytest tests/integration/test_models.py -v`

Expected: FAIL because `app.db.models` does not exist.

- [ ] **Step 3: Implement exact schema and enums**

Use timezone-aware timestamps and UUID primary keys. Define these state values exactly:

```python
class DocumentState(StrEnum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    ANALYZING = "analyzing"
    REVIEW_REQUIRED = "review_required"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    OCR_REQUIRED = "ocr_required"


class ReviewState(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EDITED = "edited"


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class RequirementCategory(StrEnum):
    ELIGIBILITY = "eligibility"
    EXCLUSION = "exclusion"
    SCHEDULE = "schedule"
    BUDGET = "budget"
    SUBMISSION = "submission"
    TECHNICAL_GOAL = "technical_goal"
    QUANTITATIVE_TARGET = "quantitative_target"
    EVALUATION = "evaluation"
    OTHER = "other"


class Importance(StrEnum):
    REQUIRED = "required"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ComplianceStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    NOT_APPLICABLE = "not_applicable"
```

Store block locators and provider usage as PostgreSQL JSONB. Give `Requirement` explicit `project_id`, `document_id`, and `analysis_job_id` foreign keys so tenant-scoped queries never depend on an unbounded relationship walk. Add indexes on `(project_id, created_at)`, `(document_id, order)`, `(project_id, state)`, and `(analysis_job_id, review_state)`. Configure database cascades rather than Python-only cascades.

In `backend/tests/conftest.py`, provide a transaction-rolled-back `db_session` fixture and a `user_factory(email: str) -> User` fixture. Integration tests must use a dedicated PostgreSQL test database; do not silently replace JSONB or cascade behavior with SQLite.

- [ ] **Step 4: Create and apply the initial migration**

Run: `cd backend && uv run alembic upgrade head`

Expected: migration `0001_initial_schema` applies with all eight tables and indexes.

- [ ] **Step 5: Run model tests**

Run: `cd backend && uv run pytest tests/integration/test_models.py -v`

Expected: PASS.

- [ ] **Step 6: Commit persistence**

```bash
git add backend/app/core/db.py backend/app/db backend/alembic.ini backend/alembic backend/tests/integration/test_models.py
git commit -m "feat: add rfp lens persistence model"
```

---

### Task 3: Authentication and project ownership

**Files:**
- Create: `backend/app/auth/schemas.py`
- Create: `backend/app/auth/service.py`
- Create: `backend/app/auth/dependencies.py`
- Create: `backend/app/auth/router.py`
- Create: `backend/app/projects/schemas.py`
- Create: `backend/app/projects/service.py`
- Create: `backend/app/projects/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/integration/test_auth_projects.py`

**Interfaces:**
- Produces: `POST /api/auth/register`, `POST /api/auth/token`, `GET /api/auth/me`.
- Produces: `GET/POST /api/projects`, `GET/PATCH/DELETE /api/projects/{project_id}`.
- Produces: `get_current_user(token, db) -> User` and `get_owned_project(db, project_id, owner_id) -> Project`.

- [ ] **Step 1: Write API tests for registration, login, and tenant isolation**

```python
def test_second_user_cannot_read_first_users_project(client) -> None:
    alice = register_and_login(client, "alice@example.com")
    project = client.post(
        "/api/projects",
        headers=alice,
        json={"name": "Alice RFP"},
    ).json()
    bob = register_and_login(client, "bob@example.com")
    response = client.get(f"/api/projects/{project['id']}", headers=bob)
    assert response.status_code == 404
```

Also assert duplicate email returns 409, wrong password returns 401, and project names reject blank or values longer than 120 characters.

Define `register_and_login(client, email) -> dict[str, str]` in the test module; it registers the email with password `Correct-Horse-2026`, requests a token, and returns the authorization header used by every ownership test.

- [ ] **Step 2: Run tests and verify routes return 404**

Run: `cd backend && uv run pytest tests/integration/test_auth_projects.py -v`

Expected: FAIL because the auth and project routes are absent.

- [ ] **Step 3: Implement password and token services**

Use `pwdlib.PasswordHash.recommended()` for Argon2 and HS256 JWT access tokens with `sub=user.id`, `iat`, and `exp`. Set access-token lifetime to 60 minutes. Normalize emails with `strip().lower()`. Return the same 401 message for unknown email and bad password.

- [ ] **Step 4: Implement ownership-scoped project services and routers**

Use this lookup rule everywhere:

```python
def get_owned_project(db: Session, project_id: UUID, owner_id: UUID) -> Project:
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.owner_id == owner_id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
```

Do not return 403 for another user's ID because that reveals resource existence.

- [ ] **Step 5: Run auth and project tests**

Run: `cd backend && uv run pytest tests/integration/test_auth_projects.py -v`

Expected: PASS.

- [ ] **Step 6: Commit identity and projects**

```bash
git add backend/app/auth backend/app/projects backend/app/main.py backend/tests/integration/test_auth_projects.py
git commit -m "feat: add authentication and project ownership"
```

---

### Task 4: Secure document upload and storage

**Files:**
- Create: `backend/app/documents/schemas.py`
- Create: `backend/app/documents/storage.py`
- Create: `backend/app/documents/validation.py`
- Create: `backend/app/documents/service.py`
- Create: `backend/app/documents/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/unit/test_document_validation.py`
- Create: `backend/tests/integration/test_document_upload.py`

**Interfaces:**
- Produces: `FileStore.save(stream, key, max_bytes) -> StoredFile`, `open(key) -> BinaryIO`, `delete(key) -> None`.
- Produces: `detect_document_format(path) -> Literal["pdf", "hwpx"]` or typed `DocumentValidationError`.
- Produces: `POST /api/projects/{project_id}/documents`, `GET /api/projects/{project_id}/documents`, and `GET/DELETE /api/projects/{project_id}/documents/{document_id}`.

- [ ] **Step 1: Write signature and size-limit tests**

```python
def test_hwpx_requires_declared_mimetype(tmp_path) -> None:
    path = build_hwpx(tmp_path / "bad.hwpx", mimetype="application/zip")
    with pytest.raises(DocumentValidationError, match="invalid_hwpx_mimetype"):
        detect_document_format(path)


def test_pdf_signature_wins_over_extension(tmp_path) -> None:
    path = tmp_path / "renamed.hwpx"
    path.write_bytes(b"%PDF-1.7\n")
    assert detect_document_format(path) == "pdf"
```

Add tests for legacy OLE header rejection, ZIP without `Contents/content.hpf`, 25 MiB stream overflow, and path sanitization that never uses the original filename as a storage path.

Define the test-local `build_hwpx(path, mimetype)` helper with Python `zipfile`; it writes the supplied root mimetype and a minimal `Contents/content.hpf`. Task 7 replaces duplicated fixture setup with the shared `hwpx_factory.py` builder.

- [ ] **Step 2: Run validation tests and verify failure**

Run: `cd backend && uv run pytest tests/unit/test_document_validation.py -v`

Expected: FAIL because the validation module is missing.

- [ ] **Step 3: Implement streaming storage and format validation**

Write uploads to a random temporary file while hashing SHA-256 and enforcing the byte limit, then atomically move to `storage_root/{owner_id}/{project_id}/{document_id}`. Validate PDF with `%PDF-`; validate HWPX as ZIP with root `mimetype` equal to `application/hwp+zip`, `Contents/content.hpf`, at most 500 entries, at most 100 MiB total uncompressed bytes, and no absolute or parent-traversal member names.

- [ ] **Step 4: Implement upload endpoints with ownership checks**

Create the `Document` row only after the file is safely stored. If the database transaction fails, delete the stored file. On project or document deletion, remove database rows and the stored object. Return error codes such as `file_too_large`, `legacy_hwp_unsupported`, `invalid_hwpx`, and `unsupported_format` in the JSON detail.

- [ ] **Step 5: Run upload tests and the complete backend suite**

Run: `cd backend && uv run pytest tests/unit/test_document_validation.py tests/integration/test_document_upload.py -v`

Expected: PASS, including cross-user upload/list/delete attempts returning 404.

- [ ] **Step 6: Commit secure ingestion**

```bash
git add backend/app/documents backend/app/main.py backend/tests
git commit -m "feat: add secure rfp document uploads"
```

---

### Task 5: Common parsing contract and registry

**Files:**
- Create: `backend/app/parsing/types.py`
- Create: `backend/app/parsing/registry.py`
- Create: `backend/app/parsing/safety.py`
- Create: `backend/tests/unit/test_parsing_contract.py`

**Interfaces:**
- Produces: `SourceLocator`, `DocumentBlock`, `ParseWarning`, and `ParseResult` Pydantic models.
- Produces: `DocumentParser.parse(path: Path) -> ParseResult` protocol.
- Produces: `ParserRegistry.get(format_name: str) -> DocumentParser`.

- [ ] **Step 1: Write contract tests**

```python
def test_document_block_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        DocumentBlock(
            block_id="pdf-p1-b1",
            order=0,
            kind="paragraph",
            text="   ",
            heading_path=[],
            locator=SourceLocator(format="pdf", page=1),
            metadata={},
        )


def test_registry_rejects_unknown_format() -> None:
    registry = ParserRegistry({})
    with pytest.raises(UnsupportedParserError):
        registry.get("hwp")
```

- [ ] **Step 2: Run contract tests and verify missing types**

Run: `cd backend && uv run pytest tests/unit/test_parsing_contract.py -v`

Expected: FAIL on missing `DocumentBlock`.

- [ ] **Step 3: Implement immutable parsing models**

Use these locator fields exactly:

```python
class SourceLocator(BaseModel, frozen=True):
    format: Literal["pdf", "hwpx"]
    page: int | None = Field(default=None, ge=1)
    bbox: tuple[float, float, float, float] | None = None
    section: str | None = None
    paragraph: int | None = Field(default=None, ge=0)
    table: int | None = Field(default=None, ge=0)
    row: int | None = Field(default=None, ge=0)
    column: int | None = Field(default=None, ge=0)
```

Require non-empty normalized text, non-negative order, unique block IDs, and at least one block in a successful `ParseResult`. Keep format adapters out of database and HTTP modules.

- [ ] **Step 4: Run parsing contract tests**

Run: `cd backend && uv run pytest tests/unit/test_parsing_contract.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the parser boundary**

```bash
git add backend/app/parsing backend/tests/unit/test_parsing_contract.py
git commit -m "feat: define format-neutral parsing contract"
```

---

### Task 6: Digital PDF parser and scanned-page detection

**Files:**
- Create: `backend/app/parsing/pdf.py`
- Create: `backend/tests/unit/test_pdf_parser.py`
- Create: `backend/tests/fixtures/pdf_factory.py`

**Interfaces:**
- Consumes: `DocumentParser`, `DocumentBlock`, `ParseResult`, and `SourceLocator` from Task 5.
- Produces: `PdfParser.parse(path) -> ParseResult` with page-based locators.

- [ ] **Step 1: Generate deterministic PDF fixtures and failing tests**

```python
def test_pdf_parser_preserves_page_locator(tmp_path) -> None:
    path = make_pdf(tmp_path / "rfp.pdf", ["1. 지원 자격\n중소기업만 신청 가능"])
    result = PdfParser().parse(path)
    assert result.blocks[0].text == "1. 지원 자격\n중소기업만 신청 가능"
    assert result.blocks[0].locator.page == 1


def test_blank_page_requires_ocr(tmp_path) -> None:
    path = make_pdf(tmp_path / "scan.pdf", [""])
    result = PdfParser(min_text_chars_per_page=20).parse(path)
    assert result.requires_ocr is True
    assert result.warnings[0].code == "ocr_required"
```

Create PDFs in tests with PyMuPDF so the repository stores no opaque binary fixtures.

- [ ] **Step 2: Run PDF tests and verify failure**

Run: `cd backend && uv run pytest tests/unit/test_pdf_parser.py -v`

Expected: FAIL because `PdfParser` does not exist.

- [ ] **Step 3: Implement paragraph and table extraction**

Open the document with PyMuPDF, reject encrypted PDFs, and iterate pages in order. Use `page.get_text("blocks", sort=True)` for paragraph candidates. Use `page.find_tables()` for detected tables, serializing each row with tab-separated cells. Exclude table bounding boxes from duplicate paragraph blocks. Normalize CRLF and repeated spaces while preserving line breaks.

Name blocks `pdf-p{page}-b{index}` and tables `pdf-p{page}-t{index}`. Infer headings only when a short line matches a Korean/Arabic numbered-title pattern such as `제1장`, `1.`, `1)`, or `가.`; carry the latest heading in `heading_path`.

- [ ] **Step 4: Mark low-text pages without running OCR**

If more than half the pages have fewer than 20 extracted characters, return `requires_ocr=True` and warning `ocr_required`. The document worker will map that result to `DocumentState.OCR_REQUIRED` and will not call the LLM.

- [ ] **Step 5: Run PDF and contract tests**

Run: `cd backend && uv run pytest tests/unit/test_pdf_parser.py tests/unit/test_parsing_contract.py -v`

Expected: PASS.

- [ ] **Step 6: Commit PDF parsing**

```bash
git add backend/app/parsing/pdf.py backend/tests/unit/test_pdf_parser.py backend/tests/fixtures/pdf_factory.py
git commit -m "feat: parse digital pdf rfp documents"
```

---

### Task 7: Safe HWPX paragraph and table parser

**Files:**
- Create: `backend/app/parsing/hwpx.py`
- Modify: `backend/app/parsing/safety.py`
- Create: `backend/tests/unit/test_hwpx_parser.py`
- Create: `backend/tests/fixtures/hwpx_factory.py`

**Interfaces:**
- Consumes: Task 5 parsing models and Task 4 package limits.
- Produces: `HwpxParser.parse(path) -> ParseResult` with section/paragraph/table locators.

- [ ] **Step 1: Build a minimal HWPX fixture and failing test**

The fixture builder must ZIP a stored root `mimetype`, `Contents/content.hpf`, and `Contents/section0.xml`. Use this body shape:

```xml
<hs:sec xmlns:hs="http://www.owpml.org/owpml/2021/section"
        xmlns:hp="http://www.owpml.org/owpml/2021/paragraph">
  <hp:p><hp:run><hp:t>1. 지원 자격</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>중소기업만 신청 가능</hp:t></hp:run></hp:p>
  <hp:tbl>
    <hp:tr><hp:tc><hp:subList><hp:p><hp:run><hp:t>평가항목</hp:t></hp:run></hp:p></hp:subList></hp:tc></hp:tr>
  </hp:tbl>
</hs:sec>
```

Assert paragraph order, heading path, table text, and locators. Add rejection tests for `../escape`, 501 members, 101 MiB declared expanded size, DTD/entity content, missing spine entries, and malformed XML.

- [ ] **Step 2: Run HWPX tests and verify failure**

Run: `cd backend && uv run pytest tests/unit/test_hwpx_parser.py -v`

Expected: FAIL because `HwpxParser` is missing.

- [ ] **Step 3: Implement safe package traversal**

Read `Contents/content.hpf` with `defusedxml.ElementTree`. Follow the OPF `spine` order to resolve section XML files; do not assume lexical filename order. Reject external entities, member names outside the archive root, duplicate resolved paths, excessive members, excessive expanded size, and compression ratios over 100:1.

- [ ] **Step 4: Implement namespace-tolerant paragraph and table extraction**

Match XML elements by local name so 2021 and later namespace URIs work. Walk each section in document order. Emit numbered short paragraphs as headings, ordinary paragraphs as paragraph blocks, and each table as one tab/newline-delimited table block. Do not emit table cell text again as standalone paragraphs. Use `hwpx-{section}-p{index}` and `hwpx-{section}-t{index}` identifiers.

- [ ] **Step 5: Run HWPX and safety tests**

Run: `cd backend && uv run pytest tests/unit/test_hwpx_parser.py tests/unit/test_document_validation.py -v`

Expected: PASS.

- [ ] **Step 6: Commit HWPX parsing**

```bash
git add backend/app/parsing backend/tests/unit/test_hwpx_parser.py backend/tests/fixtures/hwpx_factory.py
git commit -m "feat: parse safe hwpx rfp packages"
```

---

### Task 8: Celery parsing workflow and durable progress

**Files:**
- Create: `backend/app/core/celery_app.py`
- Create: `backend/app/documents/tasks.py`
- Modify: `backend/app/documents/service.py`
- Modify: `backend/app/documents/router.py`
- Modify: `backend/app/parsing/registry.py`
- Create: `backend/tests/integration/test_document_processing.py`

**Interfaces:**
- Consumes: stored documents, parser registry, database models.
- Produces: `process_document(document_id: str) -> str` Celery task.
- Produces: `POST /api/projects/{project_id}/documents/{document_id}/process` and progress fields on document GET responses.

- [ ] **Step 1: Write eager-worker state transition tests**

```python
def test_process_hwpx_persists_blocks(db_session, uploaded_hwpx) -> None:
    process_document.run(str(uploaded_hwpx.id))
    db_session.refresh(uploaded_hwpx)
    blocks = db_session.scalars(
        select(DocumentBlockRecord).where(DocumentBlockRecord.document_id == uploaded_hwpx.id)
    ).all()
    assert uploaded_hwpx.state == DocumentState.ANALYZING
    assert [block.order for block in blocks] == list(range(len(blocks)))
```

Add tests mapping scanned PDF to `OCR_REQUIRED`, malformed content to `FAILED`, and a transient storage error to retry without duplicating blocks.

Define `uploaded_hwpx` in the test module by storing a generated HWPX with `LocalFileStore`, inserting an owned project and `Document`, and returning the committed row. Keep the storage root inside pytest's `tmp_path`.

- [ ] **Step 2: Run processing tests and verify missing task**

Run: `cd backend && uv run pytest tests/integration/test_document_processing.py -v`

Expected: FAIL importing `process_document`.

- [ ] **Step 3: Configure Celery and idempotent processing**

Use Redis for broker/result backend, JSON serialization only, late acknowledgements, worker prefetch multiplier 1, and bounded retry backoff. Lock a document row with `SELECT FOR UPDATE`; replace only blocks belonging to the current unconfirmed analysis attempt. Set `PARSING` before opening the file and `ANALYZING` after blocks commit.

- [ ] **Step 4: Expose processing endpoint and progress**

Return HTTP 202 with document ID and state. Reject a second active processing request with 409 `document_already_processing`. Include `state`, `error_code`, `error_message`, `block_count`, and timestamps in document detail responses.

- [ ] **Step 5: Run processing tests**

Run: `cd backend && uv run pytest tests/integration/test_document_processing.py -v`

Expected: PASS without duplicate blocks after retries.

- [ ] **Step 6: Commit worker orchestration**

```bash
git add backend/app/core/celery_app.py backend/app/documents backend/app/parsing/registry.py backend/tests/integration/test_document_processing.py
git commit -m "feat: process rfp documents asynchronously"
```

---

### Task 9: Structured AI extraction and evidence validation

**Files:**
- Create: `backend/app/analysis/types.py`
- Create: `backend/app/analysis/chunking.py`
- Create: `backend/app/analysis/provider.py`
- Create: `backend/app/analysis/openai_provider.py`
- Create: `backend/app/analysis/fake_provider.py`
- Create: `backend/app/analysis/prompt.py`
- Create: `backend/app/analysis/validator.py`
- Create: `backend/app/analysis/service.py`
- Create: `backend/app/analysis/tasks.py`
- Modify: `backend/app/documents/tasks.py`
- Create: `backend/tests/unit/test_analysis.py`
- Create: `backend/tests/integration/test_analysis_workflow.py`
- Modify: `backend/tests/integration/test_document_processing.py`

**Interfaces:**
- Produces: `AnalysisChunk`, `ExtractedRequirement`, `ExtractionBatch`, and `ExtractionUsage`.
- Produces: `RequirementProvider.extract(chunks: list[AnalysisChunk]) -> tuple[list[ExtractedRequirement], ExtractionUsage]`.
- Produces: `run_analysis(document_id: str) -> str` Celery task.

- [ ] **Step 1: Write fake-provider and quote-verification tests**

```python
def test_unverifiable_quote_stays_pending() -> None:
    block = make_block("b1", "정부출연금은 총 5억원 이내이다.")
    extracted = ExtractedRequirement(
        requirement="정부출연금은 10억원이다",
        category=RequirementCategory.BUDGET,
        mandatory=True,
        source_block_id="b1",
        evidence_quote="정부출연금은 총 10억원 이내이다.",
        confidence="high",
    )
    validated = validate_requirement(extracted, {"b1": block})
    assert validated.evidence_verified is False
    assert validated.review_state == ReviewState.PENDING
```

Add tests for exact quote success after whitespace normalization, unknown block ID, deterministic chunk boundaries, duplicate merging, provider timeout retry, and refusal/invalid schema failure.

Define `make_block(block_id, text) -> DocumentBlock` in the test module with order `0`, kind `paragraph`, empty heading path, and a PDF page-1 locator.

- [ ] **Step 2: Run analysis tests and verify missing types**

Run: `cd backend && uv run pytest tests/unit/test_analysis.py -v`

Expected: FAIL importing analysis types.

- [ ] **Step 3: Define the strict extraction schema and prompt**

Use these fields and enum values:

```python
class ExtractedRequirement(BaseModel):
    requirement: str = Field(min_length=3, max_length=1000)
    category: RequirementCategory
    mandatory: bool
    source_block_id: str
    evidence_quote: str = Field(min_length=1, max_length=2000)
    confidence: Literal["high", "medium", "low"]
```

The Korean system prompt must state: extract only explicit requirements; never infer missing numbers or eligibility; copy evidence verbatim; return no item when evidence is absent; distinguish mandatory language from suggestions; and classify every item into the declared enum.

- [ ] **Step 4: Implement deterministic chunking and provider boundary**

Group ordered blocks without splitting a block, carrying heading paths, with a target of 12,000 Unicode characters and a hard maximum of 16,000. Tables remain atomic. Use a `Protocol` for the provider and inject it into `AnalysisService`; unit and CI tests use `FakeRequirementProvider` with fixed responses.

The provider factory accepts only `openai` and `fake`. Refuse `fake` unless `environment` is `test` or `demo`. The fake provider searches for the committed synthetic phrases and returns matching verbatim quotes so Celery-eager and Playwright tests exercise the complete persistence workflow without network.

- [ ] **Step 5: Implement the cloud adapter and local validation**

Call the OpenAI-compatible Responses structured-output endpoint with `ExtractionBatch` as the schema, `store=False`, configured model, temperature-equivalent deterministic settings when supported, and request timeout 60 seconds. Record model, prompt version `requirements-v1`, latency, and usage; never record input/output text in logs.

Normalize only Unicode width and whitespace for quote comparison. Preserve original quote for display. Merge duplicates only when category matches and normalized requirement similarity is exact after punctuation removal; attach multiple evidence rows rather than discarding sources.

- [ ] **Step 6: Persist analysis without overwriting user edits**

Create an `AnalysisJob` per run. Insert new pending requirements and evidence under that job. Do not update requirements with `CONFIRMED`, `REJECTED`, or `EDITED` review states. If every provider chunk fails, set document `FAILED`; if some fail, set `PARTIAL`; otherwise set `REVIEW_REQUIRED`.

At the end of a successful `process_document`, enqueue `run_analysis` with the document ID. In Celery eager mode, the same call runs synchronously so integration tests can assert the terminal document state and persisted requirements in one request cycle.

Update the Task 8 parsing-only integration test to monkeypatch `run_analysis.delay`; assert it receives the document ID while the parse state remains `ANALYZING`. Keep the Task 9 workflow test unpatched so it reaches `REVIEW_REQUIRED`, `PARTIAL`, or `FAILED`.

- [ ] **Step 7: Run unit and workflow tests**

Run: `cd backend && uv run pytest tests/unit/test_analysis.py tests/integration/test_analysis_workflow.py -v`

Expected: PASS using the fake provider and no network.

- [ ] **Step 8: Commit evidence-linked analysis**

```bash
git add backend/app/analysis backend/app/documents/tasks.py backend/tests/unit/test_analysis.py backend/tests/integration/test_analysis_workflow.py backend/tests/integration/test_document_processing.py
git commit -m "feat: extract and validate rfp requirements"
```

---

### Task 10: Requirement review, compliance matrix, and XLSX export APIs

**Files:**
- Create: `backend/app/compliance/schemas.py`
- Create: `backend/app/compliance/service.py`
- Create: `backend/app/compliance/router.py`
- Create: `backend/app/compliance/export.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/integration/test_compliance_api.py`
- Create: `backend/tests/unit/test_xlsx_export.py`

**Interfaces:**
- Produces: `GET /api/projects/{project_id}/requirements` with category/review-state filters.
- Produces: `PATCH /api/projects/{project_id}/requirements/{requirement_id}`.
- Produces: `GET/PATCH /api/projects/{project_id}/compliance`.
- Produces: `GET /api/projects/{project_id}/compliance.xlsx`.

- [ ] **Step 1: Write review and export tests**

```python
def test_confirming_requirement_creates_compliance_item(client, owner_headers, requirement) -> None:
    response = client.patch(
        f"/api/projects/{requirement.project_id}/requirements/{requirement.id}",
        headers=owner_headers,
        json={"review_state": "confirmed"},
    )
    assert response.status_code == 200
    matrix = client.get(
        f"/api/projects/{requirement.project_id}/compliance",
        headers=owner_headers,
    ).json()
    assert matrix[0]["requirement_id"] == str(requirement.id)
```

Add tests that edited text sets state `edited`, rejected requirements leave the matrix, unverified evidence requires an explicit `confirm_unverified=true`, another user gets 404, and XLSX headers/row values are exact.

Define `owner_headers` with the Task 3 registration helper and define `requirement` by inserting an owned project, document, block, job, requirement, and evidence in the test transaction. Use a second registered user for every 404 ownership assertion.

- [ ] **Step 2: Run tests and verify routes are absent**

Run: `cd backend && uv run pytest tests/integration/test_compliance_api.py tests/unit/test_xlsx_export.py -v`

Expected: FAIL with route/import errors.

- [ ] **Step 3: Implement atomic review and compliance services**

When a requirement becomes confirmed or edited, upsert one `ComplianceItem` with default importance `required`, blank proposal section/note, and status `not_started`. When rejected, delete its compliance item. Require optimistic concurrency through `updated_at`; stale PATCH requests return 409 `stale_update`.

- [ ] **Step 4: Implement workbook export**

Generate an in-memory workbook with sheet `컴플라이언스`. Use exact columns: `요구사항`, `분류`, `필수 여부`, `원문 근거`, `원문 위치`, `중요도`, `제안서 반영 위치`, `상태`, `메모`. Freeze the header row, enable filters, wrap text, and escape values beginning with `=`, `+`, `-`, or `@` by prefixing an apostrophe to prevent spreadsheet formula injection.

- [ ] **Step 5: Run compliance tests and all backend tests**

Run: `cd backend && uv run pytest -v`

Expected: PASS with no live AI calls.

- [ ] **Step 6: Commit review and export workflows**

```bash
git add backend/app/compliance backend/app/main.py backend/tests
git commit -m "feat: add compliance review and xlsx export"
```

---

### Task 11: Frontend shell, authentication, projects, and upload progress

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/app/api.ts`
- Create: `frontend/src/app/query-client.ts`
- Create: `frontend/src/app/router.tsx`
- Create: `frontend/src/features/auth/{AuthProvider.tsx,LoginPage.tsx,RegisterPage.tsx}`
- Create: `frontend/src/features/projects/{ProjectListPage.tsx,ProjectPage.tsx}`
- Create: `frontend/src/features/documents/{UploadPanel.tsx,ProcessingStatus.tsx}`
- Create: `frontend/src/styles.css`
- Create: `frontend/tests/upload-flow.test.tsx`

**Interfaces:**
- Consumes: auth, project, upload, processing, and document-detail APIs from Tasks 3, 4, and 8.
- Produces: routes `/login`, `/register`, `/projects`, and `/projects/:projectId`.

- [ ] **Step 1: Write a failing upload-flow component test**

```tsx
it("shows OCR guidance when the server marks a scan", async () => {
  renderProjectPageWithApi({ state: "ocr_required", error_code: "ocr_required" });
  expect(await screen.findByText("텍스트가 없는 스캔 PDF입니다"))
    .toBeInTheDocument();
  expect(screen.getByText("텍스트 PDF 또는 HWPX로 다시 업로드해 주세요"))
    .toBeInTheDocument();
});
```

Add tests for unauthenticated redirect, accepted `.pdf`/`.hwpx` picker, rejected `.hwp`, upload-size precheck, progress polling, partial result banner, and process retry button.

Add `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, and `msw` as development dependencies. Define `renderProjectPageWithApi(document)` in the test module by starting an MSW server for the project and document endpoints, creating a memory router at `/projects/project-1`, and rendering with the query and auth providers.

- [ ] **Step 2: Run frontend tests and verify the app is absent**

Run: `cd frontend && npm install && npm test -- --run`

Expected: FAIL because the frontend source files are missing.

- [ ] **Step 3: Create the typed API client and auth flow**

Store the access token in memory and `sessionStorage`, attach `Authorization: Bearer`, clear it on 401, and navigate to `/login`. Define TypeScript response types matching backend schemas; do not use `any`. Provide accessible labeled inputs and inline server validation messages.

- [ ] **Step 4: Implement project and upload pages**

Project list supports create/open/delete. Project detail supports one active upload, document history, format and size guidance, processing start/retry, and polling every two seconds only while state is `uploaded`, `parsing`, or `analyzing`. Stop polling on terminal states.

- [ ] **Step 5: Run frontend tests and production build**

Run: `cd frontend && npm test -- --run && npm run build`

Expected: tests pass and Vite creates `dist` with no TypeScript errors.

- [ ] **Step 6: Commit the usable upload workflow**

```bash
git add frontend
git commit -m "feat: add rfp upload and progress ui"
```

---

### Task 12: Evidence review and compliance matrix UI

**Files:**
- Create: `frontend/src/features/requirements/{RequirementReviewPage.tsx,RequirementCard.tsx,EvidencePanel.tsx,filters.ts}`
- Create: `frontend/src/features/compliance/{CompliancePage.tsx,ComplianceTable.tsx,ExportButton.tsx}`
- Modify: `frontend/src/app/router.tsx`
- Modify: `frontend/src/features/projects/ProjectPage.tsx`
- Create: `frontend/tests/requirement-review.test.tsx`
- Create: `frontend/tests/compliance-table.test.tsx`

**Interfaces:**
- Consumes: requirement/compliance APIs from Task 10.
- Produces: routes `/projects/:projectId/review` and `/projects/:projectId/compliance`.

- [ ] **Step 1: Write failing review interaction tests**

```tsx
it("requires confirmation before accepting unverified evidence", async () => {
  renderRequirement({ evidence_verified: false, review_state: "pending" });
  await userEvent.click(screen.getByRole("button", { name: "확정" }));
  expect(screen.getByRole("dialog", { name: "검증되지 않은 근거" }))
    .toBeInTheDocument();
  expect(mockPatch).not.toHaveBeenCalled();
});
```

Add tests for category filtering, source locator display for PDF and HWPX, editing requirement text, rejecting an item, stale-update recovery, editing compliance status/section/note, and export download filename.

Define `mockPatch` as a Vitest mock and `renderRequirement(requirement)` as a test helper that renders `RequirementCard` with `onPatch=mockPatch`; reset the mock before every test.

- [ ] **Step 2: Run tests and verify missing components**

Run: `cd frontend && npm test -- --run`

Expected: FAIL importing requirement and compliance components.

- [ ] **Step 3: Implement the review workspace**

Use a responsive two-column layout at desktop widths: requirement list left and source evidence right; stack on narrow screens. Show category, mandatory flag, confidence, verification status, source locator, exact quote, and review actions. Use `PDF p.12` locators and `HWPX Contents/section0.xml · 문단 8 · 표 2행 1열` locators without inventing page numbers.

- [ ] **Step 4: Implement editable compliance matrix and export**

Render confirmed/edited requirements with importance, proposal section, status, and note controls. Save on explicit action, send `updated_at`, and refetch on success. On 409, show a conflict banner and replace the row with the server version. Download `/compliance.xlsx` through the authenticated API client.

- [ ] **Step 5: Verify accessibility, tests, and build**

Run: `cd frontend && npm test -- --run && npm run build`

Expected: PASS with no unlabeled form controls or TypeScript failures.

- [ ] **Step 6: Commit the product's core review UI**

```bash
git add frontend/src frontend/tests
git commit -m "feat: add evidence review and compliance ui"
```

---

### Task 13: Evaluation harness, integration security, and browser flow

**Files:**
- Create: `backend/evals/__init__.py`
- Create: `backend/evals/cases/synthetic-eligibility.json`
- Create: `backend/evals/cases/synthetic-budget-table.json`
- Create: `backend/evals/metrics.py`
- Create: `backend/evals/run.py`
- Create: `backend/tests/integration/test_security_boundaries.py`
- Create: `e2e/package.json`
- Create: `e2e/playwright.config.ts`
- Create: `e2e/rfp-lens.spec.ts`
- Create: `e2e/fixtures/build-hwpx.ts`

**Interfaces:**
- Produces: `python -m evals.run --provider fake --output eval-results.json` from `backend/`.
- Produces metrics `precision`, `recall`, `evidence_verification_rate`, `latency_ms`, `input_tokens`, `output_tokens`, and `estimated_cost`.
- Produces one Playwright test for register → project → upload → process → review → export.

- [ ] **Step 1: Write metric tests before metric implementation**

```python
def test_requirement_metrics_count_false_positive() -> None:
    expected = {"지원 자격", "정부출연금 한도"}
    predicted = {"지원 자격", "정부출연금 한도", "존재하지 않는 조건"}
    result = score_requirements(expected, predicted)
    assert result.precision == pytest.approx(2 / 3)
    assert result.recall == 1.0
```

Add tests for zero predictions, evidence rates, duplicate predictions, and cost calculation using an explicit model-price configuration passed to the scorer.

- [ ] **Step 2: Implement deterministic case and result schemas**

Each case stores a `case_id`, ordered blocks, and expected requirements with category and verbatim evidence. The fake provider returns case predictions without network. Live execution requires both `--provider openai` and `ALLOW_PUBLIC_RFP_API=true`; otherwise exit with a nonzero status and a clear message.

- [ ] **Step 3: Add security regression tests**

Prove rejection of oversized uploads, forged extensions, legacy OLE HWP, ZIP traversal, excessive ZIP entries, compression ratio violations, XML entities, cross-user document IDs, cross-user requirement IDs, cross-user exports, formula-injection values, and secrets/full text absent from captured logs.

- [ ] **Step 4: Implement the browser happy path with a deterministic fake provider**

Start the API with Celery eager mode and fake provider. The Playwright test registers a unique user, creates a project, uploads the generated synthetic HWPX fixture, waits for `검토 필요`, confirms one verified requirement, fills proposal section `3. 연구개발 목표`, sets status `반영 완료`, and asserts the XLSX response has the spreadsheet content type.

Use `fflate` in `build-hwpx.ts` to create the test package at runtime with root `mimetype`, a valid `Contents/content.hpf` spine, and `Contents/section0.xml` containing the phrases consumed by `FakeRequirementProvider`. Do not commit a generated binary HWPX file.

- [ ] **Step 5: Run backend, frontend, evaluation, and browser tests**

Run: `cd backend && uv run pytest -v`

Run: `cd frontend && npm test -- --run && npm run build`

Run: `cd backend && uv run python -m evals.run --provider fake --output eval-results.json`

Run: `cd e2e && npm install && npx playwright install chromium && npm test`

Expected: every command passes without network except the one-time Playwright browser install.

- [ ] **Step 6: Commit measurable quality coverage**

```bash
git add backend/evals backend/tests/integration/test_security_boundaries.py e2e
git commit -m "test: add rfp evaluation and end-to-end coverage"
```

---

### Task 14: Containers, CI, deployment, and portfolio documentation

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Modify: `compose.yaml`
- Create: `.github/workflows/ci.yml`
- Create: `README.md`
- Create: `docs/architecture.md`
- Create: `docs/demo-script.md`

**Interfaces:**
- Produces: `docker compose up --build` services `postgres`, `redis`, `api`, `worker`, and `web`.
- Produces: CI jobs `backend`, `frontend`, `e2e`, and `container-build`.
- Produces: reproducible public/synthetic demo instructions.

- [ ] **Step 1: Write container health assertions**

Add API and web health checks to Compose and define dependencies using service health rather than startup order. The API command runs `alembic upgrade head` before Uvicorn. The worker imports the same application package and mounts no source directory in production configuration.

- [ ] **Step 2: Create non-root production images**

The backend image uses Python 3.12 slim, installs locked dependencies with `uv sync --frozen --no-dev`, and runs as an unprivileged user with a writable `/data/storage`. The frontend image builds with Node 22 and serves static assets through Nginx with `/api` proxied to the API service.

- [ ] **Step 3: Implement CI gates**

CI must run `uv run pytest`, `npm test -- --run`, `npm run build`, the fake evaluation, Playwright, and both Docker builds. Cache package downloads, not virtual environments containing secrets. Provide test-only secrets and never expose a real AI key to pull-request jobs.

- [ ] **Step 4: Write portfolio documentation with real commands and limitations**

`README.md` must include: product problem, exact commands for capturing screenshots or a GIF, architecture link, setup commands, environment variables, synthetic demo steps, test commands, evaluation metric definitions, security model, cloud-data warning, and explicit exclusions. `docs/architecture.md` must explain the common block model, PDF/HWPX locator difference, worker state machine, provider boundary, and evidence-verification trust boundary. `docs/demo-script.md` must contain a two-minute sequence using the committed synthetic HWPX fixture.

- [ ] **Step 5: Verify the release candidate from a clean checkout**

Run: `docker compose down -v`

Run: `docker compose up --build -d`

Run: `docker compose ps`

Expected: all five services are healthy.

Run: `curl http://localhost:8080/api/health`

Expected: `{"status":"ok"}`.

Run every CI command locally and complete the browser demo using synthetic data. Confirm no `.env`, uploaded file, generated workbook, evaluation output containing document text, or API credential is tracked by Git.

- [ ] **Step 6: Commit the release configuration and documentation**

```bash
git add backend/Dockerfile frontend/Dockerfile frontend/nginx.conf compose.yaml .github README.md docs
git commit -m "docs: prepare rfp lens portfolio release"
```

---

## Final verification gate

- [ ] Run `cd backend && uv run pytest -v` and record the passing count.
- [ ] Run `cd frontend && npm test -- --run && npm run build` and record the passing count.
- [ ] Run the fake evaluation and check that precision, recall, and evidence verification rate equal the committed expected values.
- [ ] Run Playwright and confirm the XLSX download assertion passes.
- [ ] Run `docker compose up --build -d`, inspect health, and complete the demo through the browser.
- [ ] Run `git status --short` and confirm only intentionally uncommitted local artifacts remain.
- [ ] Search tracked files for `OPENAI_API_KEY`, `jwt_secret`, public document full text, and incomplete-work markers; remove secrets and unfinished wording before presenting the portfolio.
