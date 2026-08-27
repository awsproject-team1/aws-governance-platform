"""Provider-neutral ports required by the read-only GitHub Repository Tool."""

from dataclasses import dataclass
from typing import Protocol

from packages.contracts._validation import require_non_empty_string


@dataclass(frozen=True, slots=True, kw_only=True)
class ApprovedRepository:
    """One Repository the customer approved for platform access."""

    repository_id: str
    owner: str
    name: str
    default_branch: str

    def __post_init__(self) -> None:
        require_non_empty_string(self.repository_id, "repository_id")
        require_non_empty_string(self.owner, "owner")
        require_non_empty_string(self.name, "name")
        require_non_empty_string(self.default_branch, "default_branch")


class ApprovalRegistry(Protocol):
    """Lookup of Repositories the customer approved."""

    def find(self, repository_id: str) -> ApprovedRepository | None:
        """Return one approved Repository by ID or None when not approved."""
        ...


class RepositoryContentSource(Protocol):
    """Read-only Repository content access through a GitHub App installation."""

    def list_paths(self, repository: ApprovedRepository, commit_sha: str) -> tuple[str, ...]:
        """Return every tracked path at one commit."""
        ...

    def read_text(self, repository: ApprovedRepository, commit_sha: str, path: str) -> str:
        """Return one file's text content at one commit."""
        ...


class SnapshotArtifactStore(Protocol):
    """Immutable storage for captured Terraform source text."""

    def put_snapshot(self, content: bytes) -> str:
        """Store snapshot bytes immutably and return an opaque reference."""
        ...


class SnapshotArtifactReader(Protocol):
    """Read-only access to captured Terraform source text.

    Consumers that analyse Terraform receive this port instead of the writer so
    they cannot replace a captured snapshot.
    """

    def get_snapshot(self, snapshot_ref: str) -> bytes:
        """Return the stored snapshot bytes for one opaque reference."""
        ...
