from app.analysis.types import AnalysisChunk
from app.parsing.types import DocumentBlock


def chunk_blocks(
    blocks: list[DocumentBlock],
    *,
    target_chars: int = 4_000,
    hard_max_chars: int = 16_000,
    overlap_blocks: int = 2,
) -> list[AnalysisChunk]:
    if (
        target_chars <= 0
        or hard_max_chars < target_chars
        or overlap_blocks < 0
    ):
        raise ValueError("Invalid chunk size limits")

    chunks: list[list[DocumentBlock]] = []
    current: list[DocumentBlock] = []
    current_chars = 0

    for block in sorted(blocks, key=lambda item: (item.order, item.block_id)):
        block_chars = len(block.text)
        if block_chars > hard_max_chars:
            raise ValueError(
                f"Block {block.block_id} exceeds the hard maximum chunk size"
            )
        if current and current_chars + block_chars > target_chars:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(block)
        current_chars += block_chars

    if current:
        chunks.append(current)

    overlapped_chunks: list[list[DocumentBlock]] = []
    for index, chunk in enumerate(chunks):
        context = (
            chunks[index - 1][-overlap_blocks:]
            if index and overlap_blocks
            else []
        )
        while context and sum(len(block.text) for block in context + chunk) > hard_max_chars:
            context = context[1:]
        overlapped_chunks.append(context + chunk)

    return [
        AnalysisChunk(chunk_id=f"chunk-{index:04d}", blocks=chunk)
        for index, chunk in enumerate(overlapped_chunks, start=1)
    ]
