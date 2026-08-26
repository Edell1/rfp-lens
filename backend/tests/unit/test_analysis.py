from types import SimpleNamespace

import pytest

from app.analysis.chunking import chunk_blocks
from app.analysis.local_provider import LocalRequirementProvider
from app.analysis.openai_provider import OpenAIRequirementProvider
from app.analysis.provider import AnalysisService, ProviderFailure
from app.analysis.service import create_requirement_provider
from app.analysis.types import ExtractedRequirement, ExtractionBatch, ExtractionUsage
from app.analysis.validator import merge_duplicates, validate_requirement
from app.core.config import Settings
from app.db.models import RequirementCategory, ReviewState
from app.parsing.types import DocumentBlock, SourceLocator


def make_block(block_id: str, text: str, order: int = 0) -> DocumentBlock:
    return DocumentBlock(
        block_id=block_id,
        order=order,
        kind="paragraph",
        text=text,
        heading_path=[],
        locator=SourceLocator(format="pdf", page=1),
        metadata={},
    )


def extracted(
    *,
    requirement: str = "정부출연금은 5억원 이내이다",
    category: RequirementCategory = RequirementCategory.BUDGET,
    block_id: str = "b1",
    quote: str = "정부출연금은 총 5억원 이내이다.",
) -> ExtractedRequirement:
    return ExtractedRequirement(
        requirement=requirement,
        category=category,
        mandatory=True,
        source_block_id=block_id,
        evidence_quote=quote,
        confidence="high",
    )


def test_unverifiable_quote_stays_pending() -> None:
    block = make_block("b1", "정부출연금은 총 5억원 이내이다.")
    item = extracted(
        requirement="정부출연금은 10억원이다",
        quote="정부출연금은 총 10억원 이내이다.",
    )

    validated = validate_requirement(item, {"b1": block})

    assert validated.evidence[0].verified is False
    assert validated.review_state == ReviewState.PENDING


def test_quote_verification_normalizes_width_and_whitespace() -> None:
    block = make_block("b1", "접수 기간은 ２０２７년   １월  ５일까지이다.")
    item = extracted(
        requirement="2027년 1월 5일까지 접수한다",
        category=RequirementCategory.SCHEDULE,
        quote="접수 기간은 2027년 1월 5일까지이다.",
    )

    validated = validate_requirement(item, {"b1": block})

    assert validated.evidence[0].verified is True


def test_unknown_block_id_is_unverified() -> None:
    validated = validate_requirement(extracted(block_id="missing"), {})

    assert validated.evidence[0].verified is False


def test_chunking_is_deterministic_and_does_not_split_blocks() -> None:
    blocks = [
        make_block("b1", "가" * 8, order=0),
        make_block("b2", "나" * 8, order=1),
        make_block("b3", "다" * 8, order=2),
    ]

    first = chunk_blocks(blocks, target_chars=16, hard_max_chars=20)
    second = chunk_blocks(list(reversed(blocks)), target_chars=16, hard_max_chars=20)

    assert [[block.block_id for block in chunk.blocks] for chunk in first] == [
        ["b1", "b2"],
        ["b3"],
    ]
    assert [chunk.model_dump() for chunk in first] == [
        chunk.model_dump() for chunk in second
    ]


def test_oversized_atomic_block_is_rejected() -> None:
    block = make_block("table", "x" * 21)

    with pytest.raises(ValueError, match="hard maximum"):
        chunk_blocks([block], target_chars=16, hard_max_chars=20)


def test_duplicate_requirements_merge_evidence_only_with_same_category() -> None:
    block1 = make_block("b1", "정부출연금은 총 5억원 이내이다.")
    block2 = make_block("b2", "정부출연금은 총 5억원 이내이다.", order=1)
    budget1 = validate_requirement(extracted(block_id="b1"), {"b1": block1})
    budget2 = validate_requirement(
        extracted(requirement="정부출연금은 5억원 이내이다!", block_id="b2"),
        {"b2": block2},
    )
    other = validate_requirement(
        extracted(category=RequirementCategory.OTHER, block_id="b2"), {"b2": block2}
    )

    merged = merge_duplicates([budget1, budget2, other])

    assert len(merged) == 2
    assert len(merged[0].evidence) == 2


def test_provider_timeout_retries_then_succeeds() -> None:
    class TimeoutThenSuccess:
        def __init__(self) -> None:
            self.calls = 0

        def extract(self, chunks):
            self.calls += 1
            if self.calls < 3:
                raise TimeoutError("temporary")
            return [extracted()], ExtractionUsage(
                provider="fake", model="fixture", prompt_version="requirements-v1"
            )

    provider = TimeoutThenSuccess()
    service = AnalysisService(provider, max_attempts=3)

    outcome = service.analyze([make_block("b1", "정부출연금은 총 5억원 이내이다.")])

    assert provider.calls == 3
    assert len(outcome.requirements) == 1
    assert outcome.failed_chunks == 0


def test_invalid_provider_result_marks_chunk_failed() -> None:
    class RefusingProvider:
        def extract(self, chunks):
            raise ProviderFailure("provider_refusal")

    outcome = AnalysisService(RefusingProvider()).analyze(
        [make_block("b1", "지원 조건이 명시되어 있다.")]
    )

    assert outcome.requirements == []
    assert outcome.failed_chunks == 1


def test_openai_adapter_requests_non_stored_structured_output() -> None:
    captured = {}

    class Responses:
        def parse(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                output_parsed=SimpleNamespace(requirements=[extracted()]),
                usage=SimpleNamespace(input_tokens=11, output_tokens=7),
            )

    client = SimpleNamespace(responses=Responses())
    provider = OpenAIRequirementProvider(
        api_key="not-used", model="test-model", client=client
    )
    chunk = chunk_blocks(
        [make_block("b1", "정부출연금은 총 5억원 이내이다.")]
    )

    requirements, usage = provider.extract(chunk)

    assert len(requirements) == 1
    assert captured["store"] is False
    assert captured["timeout"] == 60.0
    assert captured["model"] == "test-model"
    assert captured["text_format"].__name__ == "ExtractionBatch"
    assert usage.input_tokens == 11
    assert usage.output_tokens == 7


def test_fake_provider_is_rejected_outside_test_or_demo() -> None:
    settings = Settings(
        environment="production",
        jwt_secret="production-secret-that-is-long-enough",
        ai_provider="fake",
    )

    with pytest.raises(RuntimeError, match="only in test or demo"):
        create_requirement_provider(settings)


def local_settings(**overrides) -> Settings:
    return Settings(
        environment="demo",
        jwt_secret="local-provider-secret-long-enough",
        ai_provider="local",
        **overrides,
    )


def test_local_factory_requires_model_name() -> None:
    with pytest.raises(RuntimeError, match="RFP_LENS_LOCAL_MODEL"):
        create_requirement_provider(local_settings())


def test_local_factory_uses_configured_endpoint_and_model() -> None:
    provider = create_requirement_provider(
        local_settings(
            local_model="qwen2.5:7b", local_base_url="http://localhost:11434/v1"
        )
    )

    assert isinstance(provider, LocalRequirementProvider)
    assert provider.model == "qwen2.5:7b"
    assert provider.base_url == "http://localhost:11434/v1"


def test_local_adapter_sends_schema_and_parses_batch() -> None:
    captured = {}

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=ExtractionBatch(
                                requirements=[extracted()]
                            ).model_dump_json()
                        )
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=13, completion_tokens=9),
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    provider = LocalRequirementProvider(
        base_url="http://localhost:11434/v1",
        model="qwen2.5:7b",
        client=client,
    )
    chunk = chunk_blocks([make_block("b1", "정부출연금은 총 5억원 이내이다.")])

    requirements, usage = provider.extract(chunk)

    assert captured["model"] == "qwen2.5:7b"
    assert captured["response_format"]["type"] == "json_schema"
    schema = captured["response_format"]["json_schema"]["schema"]
    category = (
        schema["properties"]["requirements"]["items"]["properties"]["category"]
    )
    assert category["enum"] == [value.value for value in RequirementCategory]
    assert "$defs" not in schema and "$ref" not in str(schema)
    assert len(requirements) == 1
    assert requirements[0].evidence_quote == "정부출연금은 총 5억원 이내이다."
    assert usage.provider == "local"
    assert usage.input_tokens == 13
    assert usage.output_tokens == 9


def test_local_adapter_falls_back_to_reasoning_content() -> None:
    payload = '{"requirements": [' + extracted().model_dump_json() + "]}"

    class Completions:
        def create(self, **kwargs):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="", model_extra={"reasoning_content": payload}
                        ),
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=5, completion_tokens=20),
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    provider = LocalRequirementProvider(
        base_url="http://localhost:1234/v1", model="m", client=client
    )
    chunk = chunk_blocks([make_block("b1", "정부출연금은 총 5억원 이내이다.")])

    requirements, usage = provider.extract(chunk)

    assert len(requirements) == 1
    assert requirements[0].source_block_id == "b1"
    assert usage.output_tokens == 20


def test_local_adapter_rejects_invalid_payload() -> None:
    class Completions:
        def create(self, **kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    provider = LocalRequirementProvider(
        base_url="http://localhost:11434/v1", model="m", client=client
    )
    chunk = chunk_blocks([make_block("b1", "지원 자격 문단")])

    with pytest.raises(ProviderFailure, match="invalid extraction schema"):
        provider.extract(chunk)


def test_local_adapter_wraps_connection_errors() -> None:
    class Failing:
        def create(self, **kwargs):
            raise ConnectionError("refused")

    provider = LocalRequirementProvider(
        base_url="http://localhost:11434/v1",
        model="m",
        client=SimpleNamespace(chat=SimpleNamespace(completions=Failing())),
    )
    chunk = chunk_blocks([make_block("b1", "텍스트")])

    with pytest.raises(ProviderFailure, match="Local extraction request failed"):
        provider.extract(chunk)
