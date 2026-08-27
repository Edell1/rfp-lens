from time import monotonic
from typing import Any

from openai import OpenAI

from app.analysis.provider import ProviderFailure
from app.overview.prompt import PROMPT_VERSION, SYSTEM_PROMPT, render_summary_prompt
from app.overview.types import RequirementSummaryInput, SummaryBatch, SummaryUsage


class OpenAISummaryProvider:
    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self.model = model
        self.client = client or OpenAI(api_key=api_key, timeout=60.0, max_retries=0)

    def summarize(
        self, requirements: list[RequirementSummaryInput]
    ) -> tuple[SummaryBatch, SummaryUsage]:
        started = monotonic()
        try:
            response = self.client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": render_summary_prompt(requirements)},
                ],
                text_format=SummaryBatch,
                store=False,
                timeout=60.0,
            )
        except TimeoutError:
            raise
        except Exception as error:
            raise ProviderFailure("OpenAI summary request failed") from error
        batch = getattr(response, "output_parsed", None)
        if batch is None:
            raise ProviderFailure("OpenAI returned no structured summary")
        usage = getattr(response, "usage", None)
        return batch, SummaryUsage(
            provider="openai",
            model=self.model,
            prompt_version=PROMPT_VERSION,
            latency_ms=int((monotonic() - started) * 1000),
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        )
