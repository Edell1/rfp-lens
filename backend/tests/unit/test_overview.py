from uuid import uuid4

import pytest

from app.db.models import RequirementCategory, ReviewState
from app.overview.service import (
    calculate_stats,
    choose_effective_scope,
    source_fingerprint,
    validate_highlights,
)
from app.overview.types import RequirementSummaryInput, SummaryHighlight
from app.overview.fake_provider import FakeSummaryProvider
from app.overview.local_provider import LocalSummaryProvider
from app.overview.provider import create_summary_provider
from app.core.config import Settings


def item(
    *,
    category: RequirementCategory = RequirementCategory.ELIGIBILITY,
    state: ReviewState = ReviewState.PENDING,
    verified: bool = True,
) -> RequirementSummaryInput:
    return RequirementSummaryInput(
        id=uuid4(),
        text="중소기업만 신청 가능",
        category=category,
        mandatory=True,
        confidence="high",
        review_state=state,
        updated_at="2026-08-27T00:00:00+00:00",
        evidence_quotes=["중소기업만 신청 가능"],
        evidence_verified=[verified],
    )


def test_stats_are_project_wide_and_count_unverified_requirements_once() -> None:
    requirements = [
        item(state=ReviewState.CONFIRMED),
        item(state=ReviewState.EDITED, verified=False),
        item(state=ReviewState.PENDING, verified=False),
        item(state=ReviewState.REJECTED),
    ]

    assert calculate_stats(requirements).model_dump() == {
        "total": 4,
        "confirmed_or_edited": 2,
        "pending": 1,
        "rejected": 1,
        "unverified_evidence": 2,
    }


def test_auto_scope_uses_reviewed_only_after_review_starts() -> None:
    assert choose_effective_scope("auto", [item()]) == "all"
    assert choose_effective_scope(
        "auto", [item(state=ReviewState.CONFIRMED)]
    ) == "reviewed"
    assert choose_effective_scope("reviewed", [item()]) == "all"


def test_fingerprint_is_order_independent_and_changes_with_review_state() -> None:
    first = item()
    second = item(category=RequirementCategory.BUDGET)

    assert source_fingerprint([first, second]) == source_fingerprint([second, first])
    changed = second.model_copy(update={"review_state": ReviewState.CONFIRMED})
    assert source_fingerprint([first, second]) != source_fingerprint([first, changed])


def test_highlight_validation_removes_unknown_and_cross_category_ids() -> None:
    eligibility = item()
    budget = item(category=RequirementCategory.BUDGET)
    unknown = uuid4()
    highlights = [
        SummaryHighlight(
            category=RequirementCategory.ELIGIBILITY,
            headline="지원 대상",
            detail="중소기업 신청 자격",
            requirement_ids=[eligibility.id, budget.id, unknown],
        ),
        SummaryHighlight(
            category=RequirementCategory.BUDGET,
            headline="잘못 연결된 예산",
            detail="유효 ID 없음",
            requirement_ids=[eligibility.id],
        ),
    ]

    validated = validate_highlights(highlights, [eligibility, budget])

    assert len(validated) == 1
    assert validated[0].requirement_ids == [eligibility.id]


def test_fake_summary_provider_is_deterministic_and_evidence_linked() -> None:
    eligibility = item()
    budget = item(category=RequirementCategory.BUDGET)

    result, usage = FakeSummaryProvider().summarize([eligibility, budget])

    assert [entry.category for entry in result.highlights] == [
        RequirementCategory.ELIGIBILITY,
        RequirementCategory.BUDGET,
    ]
    assert result.highlights[0].requirement_ids == [eligibility.id]
    assert usage.provider == "fake"


def test_local_summary_provider_parses_json_schema_response() -> None:
    requirement = item(category=RequirementCategory.BUDGET)

    class Message:
        content = (
            '{"highlights":[{"category":"budget","headline":"지원 규모",'
            f'"detail":"총 지원 한도 확인","requirement_ids":["{requirement.id}"]}}]}}'
        )
        model_extra = {}

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    assert kwargs["response_format"]["type"] == "json_schema"
                    return type(
                        "Response",
                        (),
                        {
                            "choices": [
                                type("Choice", (), {"message": Message()})()
                            ],
                            "usage": None,
                        },
                    )()

    result, usage = LocalSummaryProvider(
        base_url="http://localhost:1234/v1", model="local-test", client=Client()
    ).summarize([requirement])

    assert result.highlights[0].requirement_ids == [requirement.id]
    assert usage.model == "local-test"


def test_fake_summary_provider_is_rejected_outside_test_and_demo() -> None:
    settings = Settings(environment="production", ai_provider="fake")

    with pytest.raises(RuntimeError, match="test or demo"):
        create_summary_provider(settings)
