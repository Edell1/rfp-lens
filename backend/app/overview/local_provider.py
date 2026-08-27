from time import monotonic
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from app.analysis.local_provider import _extract_json_payload
from app.analysis.provider import ProviderFailure
from app.db.models import RequirementCategory
from app.overview.prompt import PROMPT_VERSION, SYSTEM_PROMPT, render_summary_prompt
from app.overview.types import RequirementSummaryInput, SummaryBatch, SummaryUsage


SUMMARY_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "highlights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [item.value for item in RequirementCategory],
                    },
                    "headline": {"type": "string", "minLength": 1, "maxLength": 120},
                    "detail": {"type": "string", "minLength": 1, "maxLength": 300},
                    "requirement_ids": {
                        "type": "array",
                        "items": {"type": "string", "format": "uuid"},
                        "minItems": 1,
                        "maxItems": 20,
                    },
                },
                "required": ["category", "headline", "detail", "requirement_ids"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["highlights"],
    "additionalProperties": False,
}


class LocalSummaryProvider:
    def __init__(self, *, base_url: str, model: str, client: Any | None = None) -> None:
        self.model = model
        self.client = client or OpenAI(
            api_key="local", base_url=base_url, timeout=300.0, max_retries=0
        )

    def summarize(
        self, requirements: list[RequirementSummaryInput]
    ) -> tuple[SummaryBatch, SummaryUsage]:
        started = monotonic()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": render_summary_prompt(requirements)},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "analysis_summary", "schema": SUMMARY_JSON_SCHEMA},
                },
            )
        except TimeoutError:
            raise
        except Exception as error:
            raise ProviderFailure("Local summary request failed") from error
        choices = list(getattr(response, "choices", []) or [])
        message = choices[0].message if choices else None
        content = getattr(message, "content", None) or ""
        if not content.strip() and message is not None:
            content = str((getattr(message, "model_extra", None) or {}).get("reasoning_content") or "")
        try:
            batch = SummaryBatch.model_validate_json(_extract_json_payload(content))
        except ValidationError as error:
            raise ProviderFailure("Local model returned invalid summary schema") from error
        usage = getattr(response, "usage", None)
        return batch, SummaryUsage(
            provider="local",
            model=self.model,
            prompt_version=PROMPT_VERSION,
            latency_ms=int((monotonic() - started) * 1000),
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        )
