"""Assessment transport contracts for the Initial Assessment start protocol."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from packages.contracts._validation import require_non_empty_string
from packages.contracts.errors import ApiError
from packages.contracts.governance import EffectiveRuleSet
from packages.contracts.jobs import JobCurrentStep, JobStatus


class AssessmentPhase(StrEnum):
    """Governance evaluation phases."""

    INITIAL = "INITIAL"
    PRE_DEPLOY = "PRE_DEPLOY"
    POST_DEPLOY = "POST_DEPLOY"


class AssessmentStartStatus(StrEnum):
    """State returned by C after it durably creates an Assessment record."""

    ACCEPTED = "ACCEPTED"


def _require_positive_int(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value < 1:
        raise ValueError(f"{field_name} must be a positive integer")


def _require_non_negative_int(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _require_initial_phase(phase: AssessmentPhase) -> None:
    if not isinstance(phase, AssessmentPhase):
        raise TypeError("phase must be an AssessmentPhase")
    if phase is not AssessmentPhase.INITIAL:
        raise ValueError("phase must be INITIAL")


def _require_exact_fields(
    value: object,
    name: str,
    expected_fields: frozenset[str],
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    actual_fields = set(value)
    unknown_fields = sorted(actual_fields - expected_fields)
    if unknown_fields:
        raise ValueError(f"{name} has unknown field(s): {', '.join(unknown_fields)}")
    missing_fields = sorted(expected_fields - actual_fields)
    if missing_fields:
        raise ValueError(f"{name} is missing field(s): {', '.join(missing_fields)}")
    return value


def _parse_phase(value: object) -> AssessmentPhase:
    try:
        return AssessmentPhase(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("phase must be a supported AssessmentPhase") from exc


def _parse_job_status(value: object) -> JobStatus:
    try:
        return JobStatus(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("status must be a supported JobStatus") from exc


def _parse_current_step(value: object) -> JobCurrentStep:
    try:
        return JobCurrentStep(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("current_step must be a supported JobCurrentStep") from exc


def _parse_api_error(value: object) -> ApiError:
    fields = _require_exact_fields(value, "error", frozenset({"code", "message"}))
    return ApiError(code=fields["code"], message=fields["message"])


@dataclass(frozen=True, slots=True, kw_only=True)
class InitialAssessmentStartRequest:
    """Public request to start the explicit Initial Assessment flow.

    Runtime settings and scoring are resolved and pinned by the server, not supplied by
    the caller. Scope is intentionally absent until D/C agree its snapshot-inventory
    semantics.
    """

    phase: AssessmentPhase
    repository_id: str
    policy_profile_id: str
    policy_profile_version: int

    def __post_init__(self) -> None:
        _require_initial_phase(self.phase)
        require_non_empty_string(self.repository_id, "repository_id")
        require_non_empty_string(self.policy_profile_id, "policy_profile_id")
        _require_positive_int(self.policy_profile_version, "policy_profile_version")

    @classmethod
    def from_dict(cls, value: object) -> InitialAssessmentStartRequest:
        fields = _require_exact_fields(
            value,
            "initial_assessment_start_request",
            frozenset({"phase", "repository_id", "policy_profile_id", "policy_profile_version"}),
        )
        return cls(
            phase=_parse_phase(fields["phase"]),
            repository_id=fields["repository_id"],
            policy_profile_id=fields["policy_profile_id"],
            policy_profile_version=fields["policy_profile_version"],
        )

    def to_dict(self) -> dict[str, object]:
        """Return the public HTTP body wire shape."""
        return {
            "phase": self.phase.value,
            "repository_id": self.repository_id,
            "policy_profile_id": self.policy_profile_id,
            "policy_profile_version": self.policy_profile_version,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class AssessmentStartCommand:
    """A/B-to-C command with the server-pinned Assessment inputs."""

    job_id: str
    phase: AssessmentPhase
    repository_id: str
    effective_rule_set: EffectiveRuleSet
    scoring_version: str

    def __post_init__(self) -> None:
        require_non_empty_string(self.job_id, "job_id")
        _require_initial_phase(self.phase)
        require_non_empty_string(self.repository_id, "repository_id")
        if not isinstance(self.effective_rule_set, EffectiveRuleSet):
            raise TypeError("effective_rule_set must be an EffectiveRuleSet")
        if self.effective_rule_set.phase.value != self.phase.value:
            raise ValueError("effective_rule_set phase must match phase")
        require_non_empty_string(self.scoring_version, "scoring_version")

    @classmethod
    def from_dict(cls, value: object) -> AssessmentStartCommand:
        fields = _require_exact_fields(
            value,
            "assessment_start_command",
            frozenset(
                {"job_id", "phase", "repository_id", "effective_rule_set", "scoring_version"}
            ),
        )
        return cls(
            job_id=fields["job_id"],
            phase=_parse_phase(fields["phase"]),
            repository_id=fields["repository_id"],
            effective_rule_set=EffectiveRuleSet.from_dict(fields["effective_rule_set"]),
            scoring_version=fields["scoring_version"],
        )

    def to_dict(self) -> dict[str, object]:
        """Return the internal start command wire shape."""
        return {
            "job_id": self.job_id,
            "phase": self.phase.value,
            "repository_id": self.repository_id,
            "effective_rule_set": self.effective_rule_set.to_dict(),
            "scoring_version": self.scoring_version,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class AssessmentStartAcknowledgement:
    """C acknowledgement after storing, but before activating, its Assessment record."""

    job_id: str
    assessment_id: str
    status: AssessmentStartStatus = field(default=AssessmentStartStatus.ACCEPTED, init=False)

    def __post_init__(self) -> None:
        require_non_empty_string(self.job_id, "job_id")
        require_non_empty_string(self.assessment_id, "assessment_id")

    @classmethod
    def from_dict(cls, value: object) -> AssessmentStartAcknowledgement:
        fields = _require_exact_fields(
            value,
            "assessment_start_acknowledgement",
            frozenset({"job_id", "assessment_id", "status"}),
        )
        if fields["status"] != AssessmentStartStatus.ACCEPTED.value:
            raise ValueError("status must be ACCEPTED")
        return cls(job_id=fields["job_id"], assessment_id=fields["assessment_id"])

    def to_dict(self) -> dict[str, str]:
        """Return the internal C acknowledgement wire shape."""
        return {
            "job_id": self.job_id,
            "assessment_id": self.assessment_id,
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class AssessmentLinkageConfirmation:
    """A-to-C confirmation that the Job link committed at revision one."""

    job_id: str
    assessment_id: str
    revision: int
    status: JobStatus = field(default=JobStatus.RUNNING, init=False)
    current_step: JobCurrentStep = field(default=JobCurrentStep.LOAD_IAC, init=False)

    def __post_init__(self) -> None:
        require_non_empty_string(self.job_id, "job_id")
        require_non_empty_string(self.assessment_id, "assessment_id")
        _require_positive_int(self.revision, "revision")
        if self.revision != 1:
            raise ValueError("revision must be 1")

    @classmethod
    def from_dict(cls, value: object) -> AssessmentLinkageConfirmation:
        fields = _require_exact_fields(
            value,
            "assessment_linkage_confirmation",
            frozenset({"job_id", "assessment_id", "revision", "status", "current_step"}),
        )
        if _parse_job_status(fields["status"]) is not JobStatus.RUNNING:
            raise ValueError("status must be RUNNING")
        if _parse_current_step(fields["current_step"]) is not JobCurrentStep.LOAD_IAC:
            raise ValueError("current_step must be LOAD_IAC")
        return cls(
            job_id=fields["job_id"],
            assessment_id=fields["assessment_id"],
            revision=fields["revision"],
        )

    def to_dict(self) -> dict[str, object]:
        """Return the activation command sent after Job linkage commits."""
        return {
            "job_id": self.job_id,
            "assessment_id": self.assessment_id,
            "revision": self.revision,
            "status": self.status.value,
            "current_step": self.current_step.value,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class AssessmentProgressUpdate:
    """C-to-A progress update with separate ordering and duplicate-delivery keys."""

    update_id: str
    job_id: str
    assessment_id: str
    expected_revision: int
    status: JobStatus
    current_step: JobCurrentStep
    error: ApiError | None = None

    def __post_init__(self) -> None:
        require_non_empty_string(self.update_id, "update_id")
        require_non_empty_string(self.job_id, "job_id")
        require_non_empty_string(self.assessment_id, "assessment_id")
        _require_non_negative_int(self.expected_revision, "expected_revision")
        if not isinstance(self.status, JobStatus):
            raise TypeError("status must be a JobStatus")
        if not isinstance(self.current_step, JobCurrentStep):
            raise TypeError("current_step must be a JobCurrentStep")
        if self.status is JobStatus.FAILED and self.error is None:
            raise ValueError("FAILED progress updates require an ApiError")
        if self.status is not JobStatus.FAILED and self.error is not None:
            raise ValueError("only FAILED progress updates may receive an error")
        if self.error is not None and not isinstance(self.error, ApiError):
            raise TypeError("error must be an ApiError or None")

    @classmethod
    def from_dict(cls, value: object) -> AssessmentProgressUpdate:
        fields = _require_exact_fields(
            value,
            "assessment_progress_update",
            frozenset(
                {
                    "update_id",
                    "job_id",
                    "assessment_id",
                    "expected_revision",
                    "status",
                    "current_step",
                    "error",
                }
            ),
        )
        error = None if fields["error"] is None else _parse_api_error(fields["error"])
        return cls(
            update_id=fields["update_id"],
            job_id=fields["job_id"],
            assessment_id=fields["assessment_id"],
            expected_revision=fields["expected_revision"],
            status=_parse_job_status(fields["status"]),
            current_step=_parse_current_step(fields["current_step"]),
            error=error,
        )

    def to_dict(self) -> dict[str, object]:
        """Return the C-to-A progress update wire shape."""
        return {
            "update_id": self.update_id,
            "job_id": self.job_id,
            "assessment_id": self.assessment_id,
            "expected_revision": self.expected_revision,
            "status": self.status.value,
            "current_step": self.current_step.value,
            "error": None if self.error is None else self.error.to_dict(),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class AssessmentProgressAcknowledgement:
    """A response for either the first accepted progress event or its exact retry."""

    job_id: str
    update_id: str
    revision: int

    def __post_init__(self) -> None:
        require_non_empty_string(self.job_id, "job_id")
        require_non_empty_string(self.update_id, "update_id")
        _require_positive_int(self.revision, "revision")

    @classmethod
    def from_dict(cls, value: object) -> AssessmentProgressAcknowledgement:
        """Parse the acknowledgement sent on the A-to-C progress boundary."""
        fields = _require_exact_fields(
            value,
            "assessment_progress_acknowledgement",
            frozenset({"job_id", "update_id", "revision"}),
        )
        return cls(
            job_id=fields["job_id"],
            update_id=fields["update_id"],
            revision=fields["revision"],
        )

    def to_dict(self) -> dict[str, object]:
        """Return the revision applied by the first delivery of the update."""
        return {"job_id": self.job_id, "update_id": self.update_id, "revision": self.revision}


@dataclass(frozen=True, slots=True, kw_only=True)
class AssessmentAcceptedResponse:
    """Public response returned after an Initial Assessment request is accepted."""

    job_id: str
    status: JobStatus = field(default=JobStatus.QUEUED, init=False)

    def __post_init__(self) -> None:
        require_non_empty_string(self.job_id, "job_id")

    def to_dict(self) -> dict[str, str]:
        """Return the 202 Accepted response wire shape."""
        return {"job_id": self.job_id, "status": self.status.value}
