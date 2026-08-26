"""Deterministic scoring for requirement extraction quality and cost."""

from collections.abc import Iterable
from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True)
class ConfusionCounts:
    true_positives: int
    false_positives: int
    false_negatives: int


@dataclass(frozen=True)
class RequirementScores:
    precision: float
    recall: float


@dataclass(frozen=True)
class ModelPrice:
    """Price per one million tokens in USD."""

    input_per_mtok: float
    output_per_mtok: float


def normalize_requirement(value: str) -> str:
    """Normalize width, case, punctuation, and whitespace for set matching."""
    normalized = " ".join(unicodedata.normalize("NFKC", value).split()).casefold()
    without_punctuation = "".join(
        character
        for character in normalized
        if not unicodedata.category(character).startswith("P")
    )
    return "".join(without_punctuation.split())


def confusion_counts(expected: Iterable[str], predicted: Iterable[str]) -> ConfusionCounts:
    expected_set = {normalize_requirement(item) for item in expected} - {""}
    predicted_set = {normalize_requirement(item) for item in predicted} - {""}
    matches = len(expected_set & predicted_set)
    return ConfusionCounts(
        true_positives=matches,
        false_positives=len(predicted_set - expected_set),
        false_negatives=len(expected_set - predicted_set),
    )


def scores_from_counts(counts: ConfusionCounts) -> RequirementScores:
    precision_denominator = counts.true_positives + counts.false_positives
    recall_denominator = counts.true_positives + counts.false_negatives
    return RequirementScores(
        precision=(
            counts.true_positives / precision_denominator
            if precision_denominator
            else 0.0
        ),
        recall=(
            counts.true_positives / recall_denominator if recall_denominator else 0.0
        ),
    )


def score_requirements(
    expected: Iterable[str], predicted: Iterable[str]
) -> RequirementScores:
    return scores_from_counts(confusion_counts(expected, predicted))


def evidence_verification_rate(verified_flags: Iterable[bool]) -> float:
    flags = list(verified_flags)
    if not flags:
        return 0.0
    return sum(1 for flag in flags if flag) / len(flags)


def estimate_cost(
    input_tokens: int, output_tokens: int, price: ModelPrice
) -> float:
    return (
        input_tokens / 1_000_000 * price.input_per_mtok
        + output_tokens / 1_000_000 * price.output_per_mtok
    )
