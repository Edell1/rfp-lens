from time import monotonic
from typing import Any

from openai import OpenAI

from app.analysis.prompt import PROMPT_VERSION, SYSTEM_PROMPT, render_chunk_prompt
from app.analysis.provider import ProviderFailure
from app.analysis.types import AnalysisChunk, ExtractionBatch, ExtractionUsage


class OpenAIRequirementProvider:
    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self.model = model
        self.client = client or OpenAI(api_key=api_key, timeout=60.0)

    def extract(self, chunks: list[AnalysisChunk]):
        started = monotonic()
        user_prompt = "\n\n".join(
            render_chunk_prompt(
                chunk.chunk_id,
                [(block.block_id, block.text) for block in chunk.blocks],
            )
            for chunk in chunks
        )
        try:
            response = self.client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                text_format=ExtractionBatch,
                store=False,
                timeout=60.0,
            )
        except TimeoutError:
            raise
        except Exception as error:
            raise ProviderFailure("OpenAI extraction request failed") from error

        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise ProviderFailure("OpenAI returned no structured extraction")
        usage = getattr(response, "usage", None)
        return parsed.requirements, ExtractionUsage(
            provider="openai",
            model=self.model,
            prompt_version=PROMPT_VERSION,
            latency_ms=int((monotonic() - started) * 1000),
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        )
