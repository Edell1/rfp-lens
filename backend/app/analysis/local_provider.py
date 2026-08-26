from time import monotonic
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from app.analysis.prompt import PROMPT_VERSION, SYSTEM_PROMPT, render_chunk_prompt
from app.analysis.provider import ProviderFailure
from app.analysis.types import AnalysisChunk, ExtractionBatch, ExtractionUsage


class LocalRequirementProvider:
    """Calls a self-hosted OpenAI-compatible endpoint such as Ollama or vLLM."""

    def __init__(self, *, base_url: str, model: str, client: Any | None = None) -> None:
        self.base_url = base_url
        self.model = model
        self.client = client or OpenAI(api_key="local", base_url=base_url, timeout=60.0)

    def extract(
        self, chunks: list[AnalysisChunk]
    ) -> tuple[list, ExtractionUsage]:
        started = monotonic()
        user_prompt = "\n\n".join(
            render_chunk_prompt(
                chunk.chunk_id,
                [(block.block_id, block.text) for block in chunk.blocks],
            )
            for chunk in chunks
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "extraction_batch",
                        "schema": ExtractionBatch.model_json_schema(),
                    },
                },
            )
        except TimeoutError:
            raise
        except Exception as error:
            raise ProviderFailure("Local extraction request failed") from error

        choices = list(getattr(response, "choices", []) or [])
        content = (
            getattr(choices[0].message, "content", None) if choices else None
        )
        if not content:
            raise ProviderFailure("Local model returned no structured extraction")
        try:
            batch = ExtractionBatch.model_validate_json(content)
        except ValidationError as error:
            raise ProviderFailure("Local model returned invalid extraction schema") from error

        usage = getattr(response, "usage", None)
        return batch.requirements, ExtractionUsage(
            provider="local",
            model=self.model,
            prompt_version=PROMPT_VERSION,
            latency_ms=int((monotonic() - started) * 1000),
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        )
