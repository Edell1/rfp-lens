from time import monotonic
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from app.analysis.prompt import PROMPT_VERSION, SYSTEM_PROMPT, render_chunk_prompt
from app.analysis.provider import ProviderFailure
from app.analysis.types import AnalysisChunk, ExtractionBatch, ExtractionUsage
from app.db.models import RequirementCategory


# Flat, inline schema without "$ref"/"$defs": llama.cpp-based servers such as
# LM Studio and Ollama reject the nested schema emitted by model_json_schema().
EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "requirement": {"type": "string", "minLength": 3},
                    "category": {
                        "type": "string",
                        "enum": [category.value for category in RequirementCategory],
                    },
                    "mandatory": {"type": "boolean"},
                    "source_block_id": {"type": "string", "minLength": 1},
                    "evidence_quote": {"type": "string", "minLength": 1},
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                },
                "required": [
                    "requirement",
                    "category",
                    "mandatory",
                    "source_block_id",
                    "evidence_quote",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["requirements"],
    "additionalProperties": False,
}


class LocalRequirementProvider:
    """Calls a self-hosted OpenAI-compatible endpoint such as Ollama or vLLM."""

    def __init__(self, *, base_url: str, model: str, client: Any | None = None) -> None:
        self.base_url = base_url
        self.model = model
        self.client = client or OpenAI(
            api_key="local",
            base_url=base_url,
            timeout=300.0,
            max_retries=0,
        )

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
                        "schema": EXTRACTION_JSON_SCHEMA,
                    },
                },
            )
        except TimeoutError:
            raise
        except Exception as error:
            raise ProviderFailure(
                f"Local extraction request failed: {_error_summary(error)}"
            ) from error

        choices = list(getattr(response, "choices", []) or [])
        message = choices[0].message if choices else None
        content = getattr(message, "content", None) or ""
        if not content.strip():
            # Reasoning models (e.g. Qwen3 via LM Studio) may place the final
            # answer in the separate reasoning_content field.
            extra = getattr(message, "model_extra", None) or {}
            content = str(extra.get("reasoning_content") or "")
        if not content.strip():
            raise ProviderFailure("Local model returned no structured extraction")
        try:
            batch = ExtractionBatch.model_validate_json(
                _extract_json_payload(content)
            )
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


def _error_summary(error: Exception, limit: int = 200) -> str:
    message = str(error).strip().replace("\n", " ")
    return message[:limit] if message else error.__class__.__name__


def _extract_json_payload(text: str) -> str:
    """Trim stray reasoning prose around the outermost JSON object."""
    start = text.find("{")
    end = text.rfind("}")
    if 0 <= start < end:
        return text[start : end + 1]
    return text
