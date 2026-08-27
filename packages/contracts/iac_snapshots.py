"""Customer IaC Snapshot transport contracts."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from packages.contracts._validation import require_non_empty_string

_COMMIT_SHA = re.compile(r"[0-9a-f]{40}")


def _require_commit_sha(value: object, field_name: str) -> None:
    """Require a full lowercase hexadecimal Git commit digest."""
    require_non_empty_string(value, field_name)
    if _COMMIT_SHA.fullmatch(value) is None:  # type: ignore[arg-type]
        raise ValueError(f"{field_name} must be 40 lowercase hexadecimal characters")


@dataclass(frozen=True, slots=True, kw_only=True)
class IaCSnapshot:
    """Reproducible reference to one approved Repository commit's Terraform input.

    Terraform source text is preserved as an artifact and referenced by
    ``snapshot_ref``. Only the reproducibility metadata travels in this contract.
    Consumers load the captured text through a read-only artifact reader and
    decode it with :func:`decode_iac_snapshot_sources`.
    """

    repository_id: str
    commit_sha: str
    files: tuple[str, ...]
    snapshot_ref: str

    def __post_init__(self) -> None:
        require_non_empty_string(self.repository_id, "repository_id")
        _require_commit_sha(self.commit_sha, "commit_sha")
        if not isinstance(self.files, tuple):
            raise TypeError("files must be a tuple")
        if not self.files:
            raise ValueError("files must contain at least one path")
        for path in self.files:
            require_non_empty_string(path, "files entry")
        if len(set(self.files)) != len(self.files):
            raise ValueError("files must not repeat a path")
        if list(self.files) != sorted(self.files):
            raise ValueError("files must be sorted for reproducibility")
        require_non_empty_string(self.snapshot_ref, "snapshot_ref")

    def to_dict(self) -> dict[str, object]:
        """Return the complete IaCSnapshot wire shape."""
        return {
            "repository_id": self.repository_id,
            "commit_sha": self.commit_sha,
            "files": list(self.files),
            "snapshot_ref": self.snapshot_ref,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class IaCSnapshotSources:
    """Terraform source text captured for one IaCSnapshot artifact.

    This payload is the only place captured Terraform text is carried. It is
    written by the GitHub Repository Tool and read by Terraform analysis
    consumers, so both sides share this encoding.
    """

    repository_id: str
    commit_sha: str
    sources: Mapping[str, str]

    def __post_init__(self) -> None:
        require_non_empty_string(self.repository_id, "repository_id")
        _require_commit_sha(self.commit_sha, "commit_sha")
        if not isinstance(self.sources, Mapping):
            raise TypeError("sources must be a mapping")
        if not self.sources:
            raise ValueError("sources must contain at least one file")
        for path, text in self.sources.items():
            require_non_empty_string(path, "sources path")
            if not isinstance(text, str):
                raise TypeError("sources text must be a string")
        object.__setattr__(self, "sources", MappingProxyType(dict(self.sources)))

    @property
    def paths(self) -> tuple[str, ...]:
        """Return every captured path sorted for reproducible comparison."""
        return tuple(sorted(self.sources))

    def to_payload_bytes(self) -> bytes:
        """Return the deterministic artifact payload for this captured text."""
        return json.dumps(
            {
                "repository_id": self.repository_id,
                "commit_sha": self.commit_sha,
                "sources": dict(self.sources),
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")


class IaCSnapshotPayloadError(ValueError):
    """Raised when a stored snapshot payload does not satisfy the contract."""


def decode_iac_snapshot_sources(payload: object) -> IaCSnapshotSources:
    """Decode a stored artifact payload into captured Terraform source text."""
    if not isinstance(payload, bytes | bytearray):
        raise IaCSnapshotPayloadError("payload must be bytes")

    try:
        document = json.loads(bytes(payload).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IaCSnapshotPayloadError("payload is not valid UTF-8 JSON") from error

    if not isinstance(document, dict):
        raise IaCSnapshotPayloadError("payload must decode to an object")
    if set(document) != {"repository_id", "commit_sha", "sources"}:
        raise IaCSnapshotPayloadError(
            "payload must contain exactly repository_id, commit_sha, and sources"
        )

    try:
        return IaCSnapshotSources(
            repository_id=document["repository_id"],
            commit_sha=document["commit_sha"],
            sources=document["sources"],
        )
    except (TypeError, ValueError) as error:
        raise IaCSnapshotPayloadError("payload does not satisfy the sources contract") from error
