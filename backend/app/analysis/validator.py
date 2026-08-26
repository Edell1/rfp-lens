import re
import unicodedata

from app.analysis.types import (
    ExtractedRequirement,
    ValidatedEvidence,
    ValidatedRequirement,
)
from app.parsing.types import DocumentBlock


def normalize_quote(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def validate_requirement(
    item: ExtractedRequirement,
    blocks_by_id: dict[str, DocumentBlock],
) -> ValidatedRequirement:
    block = blocks_by_id.get(item.source_block_id)
    verified = bool(
        block
        and normalize_quote(item.evidence_quote) in normalize_quote(block.text)
    )
    return ValidatedRequirement(
        requirement=item.requirement,
        category=item.category,
        mandatory=item.mandatory,
        confidence=item.confidence,
        evidence=[
            ValidatedEvidence(
                source_block_id=item.source_block_id,
                quote=item.evidence_quote,
                verified=verified,
            )
        ],
    )


def _deduplication_text(value: str) -> str:
    normalized = normalize_quote(value).casefold()
    without_punctuation = "".join(
        character
        for character in normalized
        if not unicodedata.category(character).startswith("P")
    )
    return re.sub(r"\s+", "", without_punctuation)


def merge_duplicates(
    requirements: list[ValidatedRequirement],
) -> list[ValidatedRequirement]:
    merged: dict[tuple[str, str], ValidatedRequirement] = {}
    for requirement in requirements:
        key = (requirement.category.value, _deduplication_text(requirement.requirement))
        existing = merged.get(key)
        if existing is None:
            merged[key] = requirement
            continue
        evidence = list(existing.evidence)
        seen = {(item.source_block_id, item.quote) for item in evidence}
        evidence.extend(
            item
            for item in requirement.evidence
            if (item.source_block_id, item.quote) not in seen
        )
        merged[key] = existing.model_copy(update={"evidence": evidence})
    return list(merged.values())
