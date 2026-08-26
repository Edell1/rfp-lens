def normalize_block_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()
