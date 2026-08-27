"""Read-only IaCSnapshot construction for approved customer Repositories."""

import re

from packages.contracts import (
    IaCSnapshot,
    IaCSnapshotPayloadError,
    IaCSnapshotSources,
    decode_iac_snapshot_sources,
)
from tools.github.errors import (
    CommitNotFoundError,
    GitHubToolError,
    InstallationAccessError,
    NoTerraformFilesError,
    RepositoryNotApprovedError,
    SnapshotMismatchError,
    SnapshotNotFoundError,
    SnapshotStorageError,
)
from tools.github.ports import (
    ApprovalRegistry,
    RepositoryContentSource,
    SnapshotArtifactReader,
    SnapshotArtifactStore,
)

_COMMIT_SHA = re.compile(r"[0-9a-f]{40}")
_TERRAFORM_SUFFIXES = (".tf", ".tf.json")


def is_terraform_path(path: str) -> bool:
    """Report whether a Repository path is a Terraform source file."""
    return path.endswith(_TERRAFORM_SUFFIXES)


def build_iac_snapshot(
    *,
    repository_id: str,
    commit_sha: str,
    approvals: ApprovalRegistry,
    contents: RepositoryContentSource,
    artifacts: SnapshotArtifactStore,
) -> IaCSnapshot:
    """Capture one approved Repository commit's Terraform input as an IaCSnapshot.

    Approval is verified before any Repository content request is issued. The
    captured Terraform text is preserved as an artifact and only reproducibility
    metadata is returned.
    """
    if not isinstance(repository_id, str) or not repository_id.strip():
        raise RepositoryNotApprovedError("repository_id must identify an approved Repository")
    if not isinstance(commit_sha, str) or _COMMIT_SHA.fullmatch(commit_sha) is None:
        raise CommitNotFoundError("commit_sha must be 40 lowercase hexadecimal characters")

    repository = approvals.find(repository_id)
    if repository is None:
        raise RepositoryNotApprovedError("Repository is not approved for platform access")

    try:
        paths = contents.list_paths(repository, commit_sha)
    except GitHubToolError:
        raise
    except Exception as error:
        raise InstallationAccessError("Repository content listing failed") from error

    terraform_paths = tuple(sorted(path for path in paths if is_terraform_path(path)))
    if not terraform_paths:
        raise NoTerraformFilesError("approved commit contains no Terraform files")

    sources: dict[str, str] = {}
    for path in terraform_paths:
        try:
            sources[path] = contents.read_text(repository, commit_sha, path)
        except GitHubToolError:
            raise
        except Exception as error:
            raise InstallationAccessError("Repository content read failed") from error

    captured = IaCSnapshotSources(
        repository_id=repository.repository_id,
        commit_sha=commit_sha,
        sources=sources,
    )

    try:
        snapshot_ref = artifacts.put_snapshot(captured.to_payload_bytes())
    except GitHubToolError:
        raise
    except Exception as error:
        raise SnapshotStorageError("Terraform source text could not be preserved") from error

    if not isinstance(snapshot_ref, str) or not snapshot_ref.strip():
        raise SnapshotStorageError("artifact store returned an empty snapshot reference")

    return IaCSnapshot(
        repository_id=repository.repository_id,
        commit_sha=commit_sha,
        files=terraform_paths,
        snapshot_ref=snapshot_ref,
    )


def read_iac_snapshot_sources(
    *,
    snapshot: IaCSnapshot,
    reader: SnapshotArtifactReader,
) -> IaCSnapshotSources:
    """Load the Terraform source text captured for one IaCSnapshot.

    The stored payload must describe the same Repository, commit, and paths as
    the snapshot metadata. A mismatch is a Tool failure, never a Governance
    result, so consumers cannot analyse text from a different capture.
    """
    if not isinstance(snapshot, IaCSnapshot):
        raise SnapshotMismatchError("snapshot must be an IaCSnapshot")

    try:
        payload = reader.get_snapshot(snapshot.snapshot_ref)
    except GitHubToolError:
        raise
    except Exception as error:
        raise SnapshotNotFoundError("stored snapshot could not be read") from error

    try:
        captured = decode_iac_snapshot_sources(payload)
    except IaCSnapshotPayloadError as error:
        raise SnapshotMismatchError("stored snapshot payload is not usable") from error

    if captured.repository_id != snapshot.repository_id:
        raise SnapshotMismatchError("stored snapshot belongs to a different Repository")
    if captured.commit_sha != snapshot.commit_sha:
        raise SnapshotMismatchError("stored snapshot belongs to a different commit")
    if captured.paths != snapshot.files:
        raise SnapshotMismatchError("stored snapshot paths do not match the snapshot metadata")

    return captured
