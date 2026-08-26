from pathlib import Path
from typing import Literal, Protocol, TypeAlias

from pydantic import BaseModel, Field, field_validator, model_validator

from app.parsing.safety import normalize_block_text


MetadataValue: TypeAlias = str | int | float | bool | None


class SourceLocator(BaseModel, frozen=True):
    format: Literal["pdf", "hwpx"]
    page: int | None = Field(default=None, ge=1)
    bbox: tuple[float, float, float, float] | None = None
    section: str | None = None
    paragraph: int | None = Field(default=None, ge=0)
    table: int | None = Field(default=None, ge=0)
    row: int | None = Field(default=None, ge=0)
    column: int | None = Field(default=None, ge=0)


class DocumentBlock(BaseModel, frozen=True):
    block_id: str = Field(min_length=1, max_length=160)
    order: int = Field(ge=0)
    kind: Literal["heading", "paragraph", "table"]
    text: str
    heading_path: list[str]
    locator: SourceLocator
    metadata: dict[str, MetadataValue]

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = normalize_block_text(value)
        if not normalized:
            raise ValueError("Block text cannot be blank")
        return normalized


class ParseWarning(BaseModel, frozen=True):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1000)
    locator: SourceLocator | None = None


class ParseResult(BaseModel, frozen=True):
    blocks: list[DocumentBlock]
    warnings: list[ParseWarning] = Field(default_factory=list)
    requires_ocr: bool = False

    @model_validator(mode="after")
    def validate_result(self) -> "ParseResult":
        block_ids = [block.block_id for block in self.blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("Block IDs must be unique")
        if not self.requires_ocr and not self.blocks:
            raise ValueError("A successful parse requires at least one block")
        return self


class DocumentParser(Protocol):
    def parse(self, path: Path) -> ParseResult: ...
