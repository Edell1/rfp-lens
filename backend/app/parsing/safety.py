from pathlib import PurePosixPath
import posixpath
from urllib.parse import urlparse
from zipfile import ZipFile


MAX_ARCHIVE_MEMBERS = 500
MAX_ARCHIVE_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 100


class ArchiveSafetyError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def normalize_block_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def is_unsafe_archive_member(name: str) -> bool:
    member = PurePosixPath(name)
    return (
        member.is_absolute()
        or name.startswith(("/", "\\"))
        or "\\" in name
        or any(part in {"..", "."} or ":" in part for part in member.parts)
    )


def validate_archive(archive: ZipFile) -> set[str]:
    members = archive.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise ArchiveSafetyError("too_many_members")

    expanded_size = 0
    names: set[str] = set()
    for member in members:
        if is_unsafe_archive_member(member.filename):
            raise ArchiveSafetyError("unsafe_member_path")
        normalized_name = str(PurePosixPath(member.filename))
        if normalized_name in names:
            raise ArchiveSafetyError("duplicate_member_path")
        names.add(normalized_name)
        expanded_size += member.file_size
        if expanded_size > MAX_ARCHIVE_EXPANDED_BYTES:
            raise ArchiveSafetyError("expanded_size_exceeded")
        if member.file_size and (
            member.compress_size == 0
            or member.file_size / member.compress_size > MAX_ARCHIVE_COMPRESSION_RATIO
        ):
            raise ArchiveSafetyError("compression_ratio_exceeded")
    return names


def resolve_archive_reference(base_name: str, reference: str) -> str:
    parsed = urlparse(reference)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise ArchiveSafetyError("external_reference")
    if is_unsafe_archive_member(reference):
        raise ArchiveSafetyError("unsafe_reference")
    resolved = posixpath.normpath(
        posixpath.join(posixpath.dirname(base_name), parsed.path)
    )
    if is_unsafe_archive_member(resolved):
        raise ArchiveSafetyError("unsafe_reference")
    return resolved
