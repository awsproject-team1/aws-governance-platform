"""Assessment transport contract values approved for the initial slice."""

from dataclasses import dataclass, field
from enum import StrEnum

from packages.contracts._validation import require_non_empty_string
from packages.contracts.jobs import JobStatus


class AssessmentPhase(StrEnum):
    """Governance evaluation phases."""

    INITIAL = "INITIAL"
    PRE_DEPLOY = "PRE_DEPLOY"
    POST_DEPLOY = "POST_DEPLOY"


@dataclass(frozen=True, slots=True, kw_only=True)
class AssessmentAcceptedResponse:
    """Response returned after an Initial Assessment request is accepted."""

    job_id: str
    status: JobStatus = field(default=JobStatus.QUEUED, init=False)

    def __post_init__(self) -> None:
        require_non_empty_string(self.job_id, "job_id")

    def to_dict(self) -> dict[str, str]:
        """Return the 202 Accepted response wire shape."""
        return {"job_id": self.job_id, "status": self.status.value}
