# RFP Lens Design Specification

## Product goal

RFP Lens helps proposal writers inspect public Korean government R&D announcements and RFPs without losing mandatory requirements. A user uploads a PDF or HWPX document, reviews structured requirements linked to exact source evidence, and tracks whether each requirement is reflected in a proposal through a compliance matrix.

The product is a portfolio MVP, not an autonomous proposal writer. It demonstrates document parsing, asynchronous processing, structured LLM extraction, evidence validation, secure file handling, full-stack product design, testing, and deployment.

## Target user and primary workflow

The target user is a proposal writer or R&D planner who repeatedly reads Korean government R&D announcements and prepares proposals or research plans.

1. The user registers and creates a project.
2. The user uploads one public PDF or HWPX RFP to the project.
3. The server validates and stores the file, then queues parsing and analysis.
4. The UI shows the job state: uploaded, parsing, analyzing, review required, completed, partial, or failed.
5. The parser converts both formats into a shared ordered `DocumentBlock` representation.
6. The analyzer extracts requirements with a fixed schema.
7. The validator checks that every evidence quote exists in the referenced source block.
8. The user edits, confirms, or rejects each extracted requirement.
9. Confirmed requirements appear in a compliance matrix with proposal section and completion status.
10. The user exports the matrix to XLSX.

## MVP scope

### Included

- Email/password authentication with per-user project isolation.
- Project creation, listing, detail, and deletion.
- PDF and HWPX as equal first-class input formats.
- PDF text and table extraction from digitally generated PDFs.
- HWPX paragraph and table extraction from its ZIP/XML package.
- Detection of scanned PDFs that require OCR.
- Detection and rejection of legacy HWP, encrypted files, malformed files, and unsupported packages.
- Asynchronous parsing and analysis with retries and visible progress.
- Requirement categories: eligibility, exclusion, schedule, budget, submission, technical goal, quantitative target, evaluation, and other.
- Exact source locators and evidence quotes for every extracted requirement.
- Human review states: pending, confirmed, rejected, and edited.
- Compliance fields: importance, proposal section, owner note, and completion status.
- XLSX export.
- Provider-neutral LLM interface with one cloud API implementation.
- Synthetic offline fixtures and an evaluation harness for public RFP cases.
- Docker Compose development environment and CI.

### Excluded

- Legacy binary HWP parsing.
- OCR execution in the one-month MVP; scanned PDFs are detected and reported.
- Password-protected or distribution-protected documents.
- Proposal or research-plan draft generation.
- Vector database, semantic chat, and general-purpose RAG.
- Fine-tuning.
- Real-time multi-user collaboration.
- Company-confidential documents in demonstrations, fixtures, logs, or cloud API calls.

## Architecture

The repository is a monorepo with a React/TypeScript SPA, a FastAPI application, a Celery worker, PostgreSQL, and Redis. The API owns authentication, projects, uploads, requirements, compliance editing, and exports. The worker owns parsing and LLM analysis. Both processes share database models and focused domain services.

Format adapters produce the same immutable parsing type:

```python
class DocumentBlock(BaseModel):
    block_id: str
    order: int
    kind: Literal["heading", "paragraph", "table"]
    text: str
    heading_path: list[str]
    locator: SourceLocator
    metadata: dict[str, str | int | float | bool | None]
```

PDF locators use page numbers and optional bounding boxes. HWPX locators use section filename, paragraph index, and optional table row and column. HWPX page numbers are not required because pagination depends on layout and rendering settings.

The AI receives normalized text chunks, not original files. It returns strict structured requirements containing a source block ID and verbatim evidence quote. The server never treats schema compliance as factual correctness: it checks the block ID, verifies the quote against normalized source text, deduplicates requirements, and marks unverifiable output for review.

## Data model

- `User`: identity and password hash.
- `Project`: user-owned workspace.
- `Document`: original filename, media type, checksum, storage key, processing state, and error information.
- `DocumentBlockRecord`: persisted normalized block and locator JSON.
- `AnalysisJob`: attempt count, state, timestamps, provider/model metadata, token usage, and errors.
- `Requirement`: extracted text, category, mandatory flag, confidence, review state, and provenance.
- `Evidence`: requirement-to-block link plus quote and verification result.
- `ComplianceItem`: importance, proposal section, owner note, completion status, and update timestamp.

Deleting a project cascades database records and removes stored files. User edits are never overwritten by re-analysis; a new analysis creates a new job and preserves confirmed requirements unless the user explicitly replaces them.

## AI design

Local code performs file parsing, chunk construction, source selection, quote verification, and deduplication. A cloud API performs only schema-constrained requirement extraction from public text chunks.

The AI provider interface accepts a list of `AnalysisChunk` objects and returns `ExtractedRequirement` objects. The default implementation uses an OpenAI-compatible structured-output endpoint. Provider name, model name, prompt version, latency, input tokens, and output tokens are recorded for evaluation. A later Ollama or vLLM adapter can use the same interface but is not required for MVP completion.

No confidential company document may be sent to the cloud provider. The demo corpus must contain public government documents or synthetic fixtures only.

## Failure and security behavior

- Validate actual signatures and package structure instead of trusting extensions.
- Enforce configurable upload and decompressed-size limits.
- Prevent ZIP path traversal and compression bombs.
- Parse XML with external entities and network access disabled.
- Reject encrypted or malformed documents with a user-facing error code.
- Mark low-text PDF pages as `ocr_required` instead of silently producing empty analysis.
- Retry transient worker and API failures with bounded exponential backoff.
- Preserve partial parsing results and mark the document `partial` when possible.
- Never log full document text, prompts, API responses, passwords, access tokens, or API keys.
- Verify project ownership on every document, job, requirement, export, and file access.

## Quality strategy

Unit tests cover validation, PDF parsing, HWPX parsing, chunking, schema validation, evidence verification, and deduplication. Integration tests cover database ownership, upload-to-worker orchestration, retries, review updates, and XLSX export. Browser tests cover registration, project creation, upload, progress, requirement review, and export.

The evaluation harness compares extracted requirements with expected public or synthetic cases and reports requirement precision, recall, evidence verification rate, latency, and estimated API cost. CI uses deterministic fake-provider responses; live-provider evaluation is opt-in and never runs on pull requests.

## Global constraints

- Python 3.12 or newer.
- Node.js 22 or newer.
- PostgreSQL 16 or newer.
- Redis 7 or newer.
- Backend HTTP framework: FastAPI.
- Frontend: React with TypeScript and Vite.
- Database access: SQLAlchemy 2.x and Alembic.
- Background jobs: Celery with Redis broker and result backend.
- Backend tests: pytest.
- Frontend unit tests: Vitest and Testing Library.
- Browser tests: Playwright.
- External AI calls are permitted only for public or synthetic document text.
- AI output must contain a source block ID and verbatim evidence quote.
- No vector database, proposal generation, legacy HWP parser, or OCR engine in MVP.

## Completion criteria

The MVP is complete when a new user can upload a valid PDF or HWPX RFP, observe asynchronous progress, review evidence-linked requirements, edit the compliance matrix, and download an XLSX export in a deployed environment. Automated tests must prove tenant isolation, parser safety boundaries, evidence verification, and the main browser flow. The README must document architecture, limitations, evaluation results, setup, and a reproducible demo using public or synthetic data.
