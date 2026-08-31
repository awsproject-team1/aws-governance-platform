"""Read-only GitHub Repository Tool boundary.

This Tool never writes to customer infrastructure and never produces a
Governance judgement. Terraform Apply remains a GitHub Actions responsibility
after Human Approval.
"""

from tools.github.errors import (
    CommitNotFoundError,
    GitHubToolError,
    InstallationAccessError,
    NoTerraformFilesError,
    RepositoryNotApprovedError,
    SnapshotMismatchError,
    SnapshotNotFoundError,
    SnapshotStorageError,
    SnapshotTooLargeError,
)
from tools.github.ports import (
    ApprovalRegistry,
    ApprovedRepository,
    RepositoryContentSource,
    SnapshotArtifactReader,
    SnapshotArtifactStore,
)
from tools.github.snapshot import (
    MAX_SNAPSHOT_PAYLOAD_BYTES,
    MAX_TERRAFORM_FILE_BYTES,
    MAX_TERRAFORM_FILES,
    build_iac_snapshot,
    is_terraform_path,
    read_iac_snapshot_sources,
)

__all__ = [
    "MAX_SNAPSHOT_PAYLOAD_BYTES",
    "MAX_TERRAFORM_FILES",
    "MAX_TERRAFORM_FILE_BYTES",
    "ApprovalRegistry",
    "ApprovedRepository",
    "CommitNotFoundError",
    "GitHubToolError",
    "InstallationAccessError",
    "NoTerraformFilesError",
    "RepositoryContentSource",
    "RepositoryNotApprovedError",
    "SnapshotArtifactReader",
    "SnapshotArtifactStore",
    "SnapshotMismatchError",
    "SnapshotNotFoundError",
    "SnapshotStorageError",
    "SnapshotTooLargeError",
    "build_iac_snapshot",
    "is_terraform_path",
    "read_iac_snapshot_sources",
]
