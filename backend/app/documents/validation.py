from pathlib import Path, PurePosixPath
from typing import Literal
from zipfile import BadZipFile, ZipFile, is_zipfile


MAX_HWPX_MEMBERS = 500
MAX_HWPX_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_HWPX_COMPRESSION_RATIO = 100
OLE_COMPOUND_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")


class DocumentValidationError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.message = message or code
        super().__init__(f"{code}: {self.message}")


def _is_unsafe_member(name: str) -> bool:
    member = PurePosixPath(name)
    return (
        member.is_absolute()
        or name.startswith(("/", "\\"))
        or "\\" in name
        or any(part in {"..", "."} or ":" in part for part in member.parts)
    )


def _validate_hwpx(path: Path) -> None:
    try:
        with ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > MAX_HWPX_MEMBERS:
                raise DocumentValidationError("invalid_hwpx", "too_many_members")

            expanded_size = 0
            names: set[str] = set()
            for member in members:
                if _is_unsafe_member(member.filename):
                    raise DocumentValidationError("invalid_hwpx", "unsafe_member_path")
                names.add(member.filename)
                expanded_size += member.file_size
                if expanded_size > MAX_HWPX_EXPANDED_BYTES:
                    raise DocumentValidationError("invalid_hwpx", "expanded_size_exceeded")
                if member.file_size and (
                    member.compress_size == 0
                    or member.file_size / member.compress_size
                    > MAX_HWPX_COMPRESSION_RATIO
                ):
                    raise DocumentValidationError(
                        "invalid_hwpx", "compression_ratio_exceeded"
                    )

            if "mimetype" not in names:
                raise DocumentValidationError("invalid_hwpx_mimetype")
            if archive.read("mimetype") != b"application/hwp+zip":
                raise DocumentValidationError("invalid_hwpx_mimetype")
            if "Contents/content.hpf" not in names:
                raise DocumentValidationError("invalid_hwpx", "missing_content_manifest")
    except BadZipFile as error:
        raise DocumentValidationError("invalid_hwpx", "malformed_zip") from error


def detect_document_format(path: Path) -> Literal["pdf", "hwpx"]:
    with path.open("rb") as source:
        signature = source.read(8)

    if signature.startswith(b"%PDF-"):
        return "pdf"
    if signature == OLE_COMPOUND_SIGNATURE:
        raise DocumentValidationError("legacy_hwp_unsupported")
    if is_zipfile(path):
        _validate_hwpx(path)
        return "hwpx"
    raise DocumentValidationError("unsupported_format")
