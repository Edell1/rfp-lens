from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest

from app.documents.storage import FileTooLargeError, LocalFileStore, build_storage_key
from app.documents.validation import DocumentValidationError, detect_document_format


def build_hwpx(
    path: Path,
    mimetype: str = "application/hwp+zip",
    *,
    include_manifest: bool = True,
    extra_members: dict[str, bytes] | None = None,
) -> Path:
    with ZipFile(path, "w") as archive:
        archive.writestr("mimetype", mimetype, compress_type=ZIP_STORED)
        if include_manifest:
            archive.writestr("Contents/content.hpf", "<package />")
        for name, content in (extra_members or {}).items():
            archive.writestr(name, content, compress_type=ZIP_DEFLATED)
    return path


def test_hwpx_requires_declared_mimetype(tmp_path: Path) -> None:
    path = build_hwpx(tmp_path / "bad.hwpx", mimetype="application/zip")

    with pytest.raises(DocumentValidationError, match="invalid_hwpx_mimetype"):
        detect_document_format(path)


def test_pdf_signature_wins_over_extension(tmp_path: Path) -> None:
    path = tmp_path / "renamed.hwpx"
    path.write_bytes(b"%PDF-1.7\n")

    assert detect_document_format(path) == "pdf"


def test_legacy_ole_hwp_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "legacy.hwp"
    path.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1"))

    with pytest.raises(DocumentValidationError, match="legacy_hwp_unsupported"):
        detect_document_format(path)


def test_hwpx_requires_content_manifest(tmp_path: Path) -> None:
    path = build_hwpx(tmp_path / "missing.hwpx", include_manifest=False)

    with pytest.raises(DocumentValidationError, match="invalid_hwpx"):
        detect_document_format(path)


def test_hwpx_rejects_parent_traversal(tmp_path: Path) -> None:
    path = build_hwpx(
        tmp_path / "traversal.hwpx", extra_members={"../escape.xml": b"escape"}
    )

    with pytest.raises(DocumentValidationError, match="invalid_hwpx"):
        detect_document_format(path)


def test_hwpx_rejects_more_than_500_members(tmp_path: Path) -> None:
    members = {f"Contents/item-{index}.xml": b"x" for index in range(499)}
    path = build_hwpx(tmp_path / "many.hwpx", extra_members=members)

    with pytest.raises(DocumentValidationError, match="invalid_hwpx"):
        detect_document_format(path)


def test_hwpx_rejects_expanded_content_over_100_mib(tmp_path: Path) -> None:
    path = build_hwpx(
        tmp_path / "large.hwpx",
        extra_members={"Contents/large.bin": b"0" * (100 * 1024 * 1024 + 1)},
    )

    with pytest.raises(DocumentValidationError, match="invalid_hwpx"):
        detect_document_format(path)


def test_stream_overflow_leaves_no_stored_file(tmp_path: Path) -> None:
    store = LocalFileStore(tmp_path)

    with pytest.raises(FileTooLargeError, match="file_too_large"):
        store.save(BytesIO(b"123456789"), "owner/project/document", max_bytes=8)

    assert list(tmp_path.rglob("*")) == []


def test_storage_key_contains_only_server_generated_ids() -> None:
    owner_id, project_id, document_id = uuid4(), uuid4(), uuid4()

    key = build_storage_key(owner_id, project_id, document_id)

    assert key == f"{owner_id}/{project_id}/{document_id}"
    assert "rfp.pdf" not in key


@pytest.mark.parametrize("key", ["../escape", "/absolute", "owner/../../escape"])
def test_storage_rejects_unsafe_keys(tmp_path: Path, key: str) -> None:
    store = LocalFileStore(tmp_path)

    with pytest.raises(ValueError, match="unsafe_storage_key"):
        store.save(BytesIO(b"content"), key, max_bytes=100)
