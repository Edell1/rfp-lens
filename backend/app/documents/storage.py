from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import tempfile
from typing import BinaryIO, Protocol
from uuid import UUID


class FileTooLargeError(ValueError):
    def __init__(self) -> None:
        super().__init__("file_too_large")


@dataclass(frozen=True)
class StoredFile:
    key: str
    path: Path
    size: int
    checksum_sha256: str


class FileStore(Protocol):
    def save(self, stream: BinaryIO, key: str, max_bytes: int) -> StoredFile: ...

    def open(self, key: str) -> BinaryIO: ...

    def delete(self, key: str) -> None: ...


def build_storage_key(owner_id: UUID, project_id: UUID, document_id: UUID) -> str:
    return f"{owner_id}/{project_id}/{document_id}"


class LocalFileStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _resolve(self, key: str) -> Path:
        posix_key = PurePosixPath(key)
        if (
            not key
            or posix_key.is_absolute()
            or "\\" in key
            or any(part in {"", ".", ".."} or ":" in part for part in posix_key.parts)
        ):
            raise ValueError("unsafe_storage_key")

        root = self.root.resolve()
        target = root.joinpath(*posix_key.parts).resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise ValueError("unsafe_storage_key") from error
        return target

    def save(self, stream: BinaryIO, key: str, max_bytes: int) -> StoredFile:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        digest = hashlib.sha256()
        size = 0
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=target.parent, prefix=".upload-", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise FileTooLargeError
                    temporary.write(chunk)
                    digest.update(chunk)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, target)
        except BaseException:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            self._remove_empty_parents(target.parent)
            raise

        return StoredFile(
            key=key,
            path=target,
            size=size,
            checksum_sha256=digest.hexdigest(),
        )

    def open(self, key: str) -> BinaryIO:
        return self._resolve(key).open("rb")

    def delete(self, key: str) -> None:
        target = self._resolve(key)
        target.unlink(missing_ok=True)
        self._remove_empty_parents(target.parent)

    def _remove_empty_parents(self, directory: Path) -> None:
        root = self.root.resolve()
        current = directory
        while current != root:
            try:
                current.rmdir()
            except (FileNotFoundError, OSError):
                return
            current = current.parent
