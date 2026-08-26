from pathlib import Path
from typing import Literal
from zipfile import BadZipFile, ZipFile, is_zipfile

from app.parsing.safety import ArchiveSafetyError, validate_archive

OLE_COMPOUND_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")


class DocumentValidationError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.message = message or code
        super().__init__(f"{code}: {self.message}")


def _validate_hwpx(path: Path) -> None:
    try:
        with ZipFile(path) as archive:
            try:
                names = validate_archive(archive)
            except ArchiveSafetyError as error:
                raise DocumentValidationError("invalid_hwpx", error.reason) from error

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
