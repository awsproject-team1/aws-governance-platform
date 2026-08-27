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
    SnapshotStorageError,
)
from tools.github.ports import (
    ApprovalRegistry,
    ApprovedRepository,
    RepositoryContentSource,
    SnapshotArtifactStore,
)
from tools.github.snapshot import build_iac_snapshot, is_terraform_path

__all__ = [
    "ApprovalRegistry",
    "ApprovedRepository",
    "CommitNotFoundError",
    "GitHubToolError",
    "InstallationAccessError",
    "NoTerraformFilesError",
    "RepositoryContentSource",
    "RepositoryNotApprovedError",
    "SnapshotArtifactStore",
    "SnapshotStorageError",
    "build_iac_snapshot",
    "is_terraform_path",
]
