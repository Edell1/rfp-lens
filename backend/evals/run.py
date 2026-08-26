"""Command-line runner for requirement extraction evaluations."""

from argparse import ArgumentParser
import json
import os
from pathlib import Path
import sys

from pydantic import BaseModel, Field
from typing import Literal

from app.analysis.prompt import PROMPT_VERSION
from app.analysis.provider import AnalysisService
from app.analysis.service import create_requirement_provider
from app.core.config import Settings
from app.db.models import RequirementCategory
from app.parsing.types import DocumentBlock, SourceLocator
from evals.metrics import (
    ConfusionCounts,
    ModelPrice,
    confusion_counts,
    estimate_cost,
    evidence_verification_rate,
    scores_from_counts,
)

CASES_DIR = Path(__file__).resolve().parent / "cases"

# Explicit price table per one million tokens in USD.
MODEL_PRICES: dict[str, ModelPrice] = {
    "synthetic-fixture-v1": ModelPrice(input_per_mtok=0.0, output_per_mtok=0.0),
}

FAKE_PROVIDER_MODEL = "synthetic-fixture-v1"


class CaseBlock(BaseModel):
    block_id: str
    order: int = Field(ge=0)
    kind: Literal["heading", "paragraph", "table"]
    text: str
    heading_path: list[str] = Field(default_factory=list)
    locator: dict[str, object]


class ExpectedRequirement(BaseModel):
    requirement: str
    category: RequirementCategory
    mandatory: bool = True
    source_block_id: str
    evidence_quote: str


class EvalCase(BaseModel):
    case_id: str
    description: str = ""
    blocks: list[CaseBlock]
    expected: list[ExpectedRequirement]


def load_cases(cases_dir: Path = CASES_DIR) -> list[EvalCase]:
    cases = [
        EvalCase.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(cases_dir.glob("*.json"))
    ]
    if not cases:
        raise RuntimeError(f"No evaluation cases found in {cases_dir}")
    return cases


def build_provider(provider_name: str):
    settings = Settings(ai_provider=provider_name, environment="demo")
    return create_requirement_provider(settings)


def evaluate_case(case: EvalCase, service: AnalysisService) -> dict:
    blocks = [
        DocumentBlock(
            block_id=block.block_id,
            order=block.order,
            kind=block.kind,
            text=block.text,
            heading_path=block.heading_path,
            locator=SourceLocator.model_validate(block.locator),
            metadata={},
        )
        for block in case.blocks
    ]
    outcome = service.analyze(blocks)
    counts = confusion_counts(
        [item.requirement for item in case.expected],
        [item.requirement for item in outcome.requirements],
    )
    scores = scores_from_counts(counts)
    verified_flags = [
        evidence.verified
        for requirement in outcome.requirements
        for evidence in requirement.evidence
    ]
    return {
        "case_id": case.case_id,
        "description": case.description,
        "precision": scores.precision,
        "recall": scores.recall,
        "true_positives": counts.true_positives,
        "false_positives": counts.false_positives,
        "false_negatives": counts.false_negatives,
        "expected_count": len(case.expected),
        "predicted_count": len(outcome.requirements),
        "verified_evidence": sum(1 for flag in verified_flags if flag),
        "total_evidence": len(verified_flags),
        "latency_ms": outcome.usage.latency_ms,
        "input_tokens": outcome.usage.input_tokens,
        "output_tokens": outcome.usage.output_tokens,
        "model": outcome.usage.model,
    }


def run_evaluation(
    provider_name: str,
    cases_dir: Path = CASES_DIR,
    model_prices: dict[str, ModelPrice] | None = None,
) -> dict:
    prices = MODEL_PRICES if model_prices is None else model_prices
    provider = build_provider(provider_name)
    service = AnalysisService(provider)

    cases = load_cases(cases_dir)
    case_results = [evaluate_case(case, service) for case in cases]

    overall = scores_from_counts(
        ConfusionCounts(
            true_positives=sum(result["true_positives"] for result in case_results),
            false_positives=sum(result["false_positives"] for result in case_results),
            false_negatives=sum(result["false_negatives"] for result in case_results),
        )
    )

    total_verified = sum(result["verified_evidence"] for result in case_results)
    total_evidence = sum(result["total_evidence"] for result in case_results)
    latency_ms = sum(result["latency_ms"] for result in case_results)
    input_tokens = sum(result["input_tokens"] for result in case_results)
    output_tokens = sum(result["output_tokens"] for result in case_results)
    models = {result["model"] for result in case_results} or {"unknown"}
    model_name = next(iter(models))
    estimated_cost = estimate_cost(
        input_tokens,
        output_tokens,
        prices.get(model_name, ModelPrice(input_per_mtok=0.0, output_per_mtok=0.0)),
    )

    return {
        "provider": provider_name,
        "model": model_name,
        "prompt_version": PROMPT_VERSION,
        "cases": [
            {key: value for key, value in result.items() if key != "model"}
            for result in case_results
        ],
        "metrics": {
            "precision": overall.precision,
            "recall": overall.recall,
            "evidence_verification_rate": (
                total_verified / total_evidence if total_evidence else 0.0
            ),
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost": estimated_cost,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(description="Run RFP Lens extraction evaluations.")
    parser.add_argument("--provider", choices=["fake", "openai"], default="fake")
    parser.add_argument("--output", type=Path, default=Path("eval-results.json"))
    parser.add_argument("--cases-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.provider == "openai" and (
        os.getenv("ALLOW_PUBLIC_RFP_API", "").strip().lower() != "true"
    ):
        print(
            "Live evaluation sends case text to the cloud AI provider.\n"
            "Set ALLOW_PUBLIC_RFP_API=true together with --provider openai "
            "and RFP_LENS_OPENAI_API_KEY to allow it.",
            file=sys.stderr,
        )
        return 2

    results = run_evaluation(args.provider, cases_dir=args.cases_dir or CASES_DIR)
    args.output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    metrics = results["metrics"]
    print(f"provider: {results['provider']} model: {results['model']}")
    for result in results["cases"]:
        print(
            f"case {result['case_id']}: precision={result['precision']:.3f} "
            f"recall={result['recall']:.3f} "
            f"evidence={result['verified_evidence']}/{result['total_evidence']}"
        )
    print(
        f"overall: precision={metrics['precision']:.3f} "
        f"recall={metrics['recall']:.3f} "
        f"evidence_verification_rate={metrics['evidence_verification_rate']:.3f}"
    )
    print(
        f"latency_ms={metrics['latency_ms']} tokens_in={metrics['input_tokens']} "
        f"tokens_out={metrics['output_tokens']} "
        f"estimated_cost=${metrics['estimated_cost']:.6f}"
    )
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
