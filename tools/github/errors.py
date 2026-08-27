"""GitHub Tool execution failures.

These failures describe Tool execution problems only. They never express a
Governance judgement and must not be converted into an assessment FAIL.
"""


class GitHubToolError(RuntimeError):
    """Base failure for a GitHub Tool operation."""


class RepositoryNotApprovedError(GitHubToolError):
    """Raised when a Repository was not approved for platform access."""


class CommitNotFoundError(GitHubToolError):
    """Raised when the requested commit does not exist in the Repository."""


class InstallationAccessError(GitHubToolError):
    """Raised when the GitHub App installation cannot access the Repository."""


class NoTerraformFilesError(GitHubToolError):
    """Raised when an approved commit contains no Terraform files."""


class SnapshotStorageError(GitHubToolError):
    """Raised when Terraform source text could not be preserved."""
