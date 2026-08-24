# RFP Lens

RFP Lens는 한국 정부 R&D 공고문과 RFP를 PDF/HWPX에서 분석해, 제안서 작성자가 놓치기 쉬운 요구사항을 원문 근거와 함께 검토하고 컴플라이언스 매트릭스로 관리하도록 돕는 포트폴리오 프로젝트입니다.

## 핵심 기능

- PDF와 HWPX 문서의 제목·문단·표 구조화
- 지원 자격, 제외 조건, 일정, 예산, 제출물, 기술 목표, 정량지표, 평가기준 추출
- 모든 AI 추출 결과를 원문 블록 및 인용문과 연결
- 사용자 확인·수정·거절을 거치는 검토 흐름
- 제안서 반영 위치와 진행 상태를 관리하는 컴플라이언스 매트릭스
- XLSX 내보내기

## 설계 원칙

- 문서 파싱과 근거 검증은 로컬에서 수행합니다.
- 외부 AI API에는 공개 또는 합성 문서의 정규화된 텍스트 블록만 전송합니다.
- AI가 제안서 전체를 대신 작성하지 않습니다.
- 구형 HWP, OCR 실행, 벡터 검색, 실시간 협업은 한 달 MVP 범위에서 제외합니다.
- 실제 회사 문서와 비공개 기술자료는 예제·로그·AI 호출에 사용하지 않습니다.

## 기술 방향

- Backend: Python 3.12, FastAPI, SQLAlchemy, PostgreSQL, Celery, Redis
- Document: PyMuPDF, HWPX ZIP/XML parser, defusedxml
- AI: provider-neutral structured extraction, cloud API default
- Frontend: React, TypeScript, Vite, TanStack Query
- Quality: pytest, Vitest, Testing Library, Playwright, evaluation harness
- Delivery: Docker Compose, CI

## 문서

- [설계 명세](docs/superpowers/specs/2026-08-24-rfp-lens-design.md)
- [상세 구현 계획](docs/superpowers/plans/2026-08-24-rfp-lens-implementation.md)

현재 저장소에는 합의된 설계와 구현 계획만 기록되어 있습니다. 구현은 계획의 Task 1부터 테스트 주도로 진행합니다.
