# RFP Lens 2분 데모 스크립트

네트워크 호출 없이 합성 데이터로 제품 전체 흐름을 시연합니다. 바이너리 픽스처는 커밋하지 않고, 저장소의 `hwpx_factory`로 실행 시점에 생성합니다.

## 0. 준비 (사전 녹화 권장, 약 2분)

```bash
git clone https://github.com/Edell1/rfp-lens && cd rfp-lens
cp .env.example .env
# .env에서 다음 두 값을 설정:
#   RFP_LENS_ENVIRONMENT=demo
#   RFP_LENS_AI_PROVIDER=fake

docker compose up --build -d
docker compose ps          # 5개 서비스 모두 healthy 확인

# 데모용 합성 HWPX 생성 (커밋된 팩토리 사용)
cd backend && uv run python -c "from pathlib import Path; from tests.fixtures.hwpx_factory import build_hwpx; build_hwpx(Path('../synthetic-rfp.hwpx'))" && cd ..
```

`synthetic-rfp.hwpx`에는 fake provider가 인식하는 문구("중소기업만 신청 가능", "정부출연금은 총 5억원 이내이다.")가 들어 있습니다.

## 1. 회원가입 (0:00–0:15)

1. http://localhost:8080 접속 → 자동으로 로그인 화면.
2. "분석 공간 만들기" 링크에서 이메일/비밀번호 입력 → **계정 만들기**.
3. 프로젝트 목록(`/projects`)으로 이동하는지 확인.

## 2. 프로젝트 생성 (0:15–0:25)

1. "새 프로젝트 이름"에 `2027 스마트제조 R&D` 입력 → **프로젝트 만들기**.
2. 생성된 카드의 **열기** 클릭.

## 3. 공고문 업로드 & 분석 (0:25–0:50)

1. **파일 선택**에서 `synthetic-rfp.hwpx` 업로드.
2. "분석을 시작할 준비가 됐어요" 카드에서 **분석 시작** 클릭.
3. 상태가 "검토할 요구사항이 준비됐어요"로 바뀌는지 확인 (fake provider라 즉시 완료).
4. 우측 상단 **요구사항 검토** 클릭.

## 4. 근거 기반 요구사항 검토 — 핵심 장면 (0:50–1:20)

1. 추출된 요구사항 카드에서 분류(지원 자격), 필수 여부, 근거 인용을 확인.
2. 오른쪽 근거 패널의 원문 위치(`HWPX Contents/section0.xml · 문단 …`)를 짚어준다 — "AI가 만든 게 아니라 원문 어디에 있는지 항상 보여줍니다."
3. 첫 카드의 **확정** 클릭 → 상태 배지가 "확정"으로 변경.

> 포인트: 미검증 근거는 확정 시 별도 확인 대화상자가 뜹니다(합성 데이터는 전부 검증됨).

## 5. 컴플라이언스 매트릭스 & XLSX 내보내기 (1:20–1:50)

1. **컴플라이언스 표** 클릭.
2. 행에서 제안서 반영 위치에 `3. 연구개발 목표`, 상태를 **완료**로 변경 → **저장**.
3. **Excel 내보내기** 클릭 → `compliance.xlsx` 다운로드.
4. 파일을 열어 요구사항·근거·위치·상태 열이 채워져 있는지 확인.

## 6. 마무리 멘트 (1:50–2:00)

- "모든 요구사항에 원문 인용과 위치가 붙습니다. 검증 안 된 근거는 사람이 직접 확인해야 확정됩니다."
- 실서비스에서는 OpenAI structured outputs로 동일 파이프라인이 동작하며, 기밀 문서는 넣지 않습니다(README의 클라우드 데이터 경고).

## 트러블슈팅

| 증상 | 해결 |
| --- | --- |
| 서비스가 healthy로 안 됨 | `docker compose logs api worker` 확인, JWT_SECRET 기본값 사용 여부 점검 |
| 업로드가 거부됨 | `.hwpx`/`.pdf`인지, 25MiB 이하인지 확인 |
| 분석 후 요구사항이 비어 있음 | fake provider는 합성 문구만 인식 — 데모용 픽스처를 그대로 사용 |
