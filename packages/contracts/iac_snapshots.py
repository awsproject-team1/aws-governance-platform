"""Customer IaC Snapshot transport contracts."""

import re
from dataclasses import dataclass

from packages.contracts._validation import require_non_empty_string

_COMMIT_SHA = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True, slots=True, kw_only=True)
class IaCSnapshot:
    """Reproducible reference to one approved Repository commit's Terraform input.

    Terraform source text is preserved as an artifact and referenced by
    ``snapshot_ref``. Only the reproducibility metadata travels in this contract.
    """

    repository_id: str
    commit_sha: str
    files: tuple[str, ...]
    snapshot_ref: str

    def __post_init__(self) -> None:
        require_non_empty_string(self.repository_id, "repository_id")
        require_non_empty_string(self.commit_sha, "commit_sha")
        if _COMMIT_SHA.fullmatch(self.commit_sha) is None:
            raise ValueError("commit_sha must be 40 lowercase hexadecimal characters")
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
