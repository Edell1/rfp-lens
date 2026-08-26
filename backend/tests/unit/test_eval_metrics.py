import json

import pytest

from evals.metrics import (
    ConfusionCounts,
    ModelPrice,
    confusion_counts,
    estimate_cost,
    evidence_verification_rate,
    score_requirements,
    scores_from_counts,
)
from evals.run import run_evaluation


def test_requirement_metrics_count_false_positive() -> None:
    expected = {"지원 자격", "정부출연금 한도"}
    predicted = {"지원 자격", "정부출연금 한도", "존재하지 않는 조건"}

    result = score_requirements(expected, predicted)

    assert result.precision == pytest.approx(2 / 3)
    assert result.recall == 1.0


def test_zero_predictions_score_zero() -> None:
    result = score_requirements({"지원 자격"}, set())

    assert result.precision == 0.0
    assert result.recall == 0.0


def test_empty_case_is_perfect_by_convention() -> None:
    result = scores_from_counts(confusion_counts([], []))

    assert result.precision == 0.0
    assert result.recall == 0.0


def test_duplicate_predictions_count_once() -> None:
    result = score_requirements({"지원 자격", "예산"}, ["지원 자격", "지원 자격"])

    assert result.precision == 1.0
    assert result.recall == pytest.approx(0.5)


def test_width_and_punctuation_do_not_change_matching() -> None:
    result = score_requirements(
        {"정부출연금은 5억원 이내이다."}, {"정부출연금은 ５억원 이내이다"}
    )

    assert result.precision == 1.0
    assert result.recall == 1.0


@pytest.mark.parametrize(
    ("flags", "expected_rate"),
    [
        ([], 0.0),
        ([True], 1.0),
        ([False], 0.0),
        ([True, True, False], pytest.approx(2 / 3)),
        ([True, False, False, False], pytest.approx(1 / 4)),
    ],
)
def test_evidence_verification_rate(flags: list[bool], expected_rate: float) -> None:
    assert evidence_verification_rate(flags) == expected_rate


def test_cost_uses_explicit_model_price_configuration() -> None:
    price = ModelPrice(input_per_mtok=0.30, output_per_mtok=1.20)

    cost = estimate_cost(input_tokens=2_000_000, output_tokens=500_000, price=price)

    assert cost == pytest.approx(0.60 + 0.60)


def test_counts_are_pooled_across_cases() -> None:
    pooled = ConfusionCounts(true_positives=3, false_positives=1, false_negatives=1)

    result = scores_from_counts(pooled)

    assert result.precision == pytest.approx(3 / 4)
    assert result.recall == pytest.approx(3 / 4)


def test_fake_evaluation_matches_committed_expectations(tmp_path) -> None:
    results = run_evaluation("fake")
    output = tmp_path / "eval-results.json"
    output.write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")

    metrics = results["metrics"]
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["evidence_verification_rate"] == 1.0
    assert metrics["estimated_cost"] == 0.0
    assert metrics["input_tokens"] == 0
    assert metrics["output_tokens"] == 0
    assert [case["case_id"] for case in results["cases"]] == [
        "synthetic-budget-table",
        "synthetic-eligibility",
    ]
