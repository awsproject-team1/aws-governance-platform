"""Area B governance contracts.

Only shape, enum, identity, and primitive-format validation belongs here.
Registry membership and lifecycle policy stay in ``packages.governance``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

RULE_ID_PATTERN = re.compile(r"^(GLOBAL|CUSTOMER)-[A-Z0-9]+-[A-Z0-9]+-[0-9]{3}$")
TOKEN_PATTERN = re.compile(r"[A-Z][A-Z0-9_]*")
SCORING_VERSION_PATTERN = re.compile(r"[1-9][0-9]*")
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class ContractValidationError(ValueError):
    """Raised when untrusted data does not match an executable contract."""


class SourceType(str, Enum):
    GLOBAL = "GLOBAL"
    CUSTOMER = "CUSTOMER"


class RuleStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"


class EvaluationType(str, Enum):
    IAC = "IAC"
    AWS = "AWS"
    HYBRID = "HYBRID"
    MANUAL = "MANUAL"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AssessmentPhase(str, Enum):
    """Phase of one Assessment execution; owned by the Assessment contract."""

    INITIAL = "INITIAL"
    PRE_DEPLOY = "PRE_DEPLOY"
    POST_DEPLOY = "POST_DEPLOY"


class RuleSetPhase(str, Enum):
    """Effective Rule Set selection mode.

    Superset of ``AssessmentPhase``: ``MANUAL_REVIEW`` selects the rules a person
    resolves outside the IaC/AWS evaluation path, so it is not an Assessment phase.
    """

    INITIAL = "INITIAL"
    PRE_DEPLOY = "PRE_DEPLOY"
    POST_DEPLOY = "POST_DEPLOY"
    MANUAL_REVIEW = "MANUAL_REVIEW"

    @classmethod
    def for_assessment(cls, phase: AssessmentPhase) -> RuleSetPhase:
        return cls(AssessmentPhase(phase).value)

    @property
    def assessment_phase(self) -> AssessmentPhase | None:
        """The Assessment phase this selection belongs to, or None for MANUAL_REVIEW."""
        if self is RuleSetPhase.MANUAL_REVIEW:
            return None
        return AssessmentPhase(self.value)


class EvaluationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    # wire value에 "N/A"를 쓰지 않는다. 이 값은 C가 URL path segment, DynamoDB sort key,
    # S3 prefix, CloudWatch metric dimension에 그대로 싣는 자리로 가는데 슬래시가 들어가면
    # 경계마다 escaping 규칙이 갈린다. 화면 표기는 Frontend가 따로 정한다.
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class EvidenceResultStatus(str, Enum):
    FOUND = "FOUND"
    NOT_FOUND = "NOT_FOUND"
    ERROR = "ERROR"


def _mapping(value: Any, name: str, allowed: frozenset[str]) -> Mapping[str, Any]:
    """Reject unknown keys instead of discarding them.

    Silently dropping an unknown key turns a Consumer typo into wrong data rather than a
    validation error. ``sevirity`` would be discarded while ``severity`` keeps whatever the
    payload happened to carry, and severity is the scoring weight, so the result is a wrong
    compliance score with nothing reported. This is the B-to-C boundary, so the contract has
    to say no.
    """
    if not isinstance(value, Mapping):
        raise ContractValidationError(f"{name} must be an object")
    unknown = sorted(key for key in value if key not in allowed)
    if unknown:
        raise ContractValidationError(f"{name} has unknown field(s): {', '.join(unknown)}")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{name} must be a non-empty string")
    return value


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ContractValidationError(f"{name} must be a positive integer")
    return value


def _hash(value: Any, name: str) -> str:
    value = _text(value, name)
    if not HASH_PATTERN.fullmatch(value):
        raise ContractValidationError(f"{name} must be a lowercase sha256 digest")
    return value


def _token(value: Any, name: str) -> str:
    """Constrain the token shape without deciding the vocabulary.

    ``remediation_type`` is still a free-form ``str`` because its full enum is an Open
    Decision owned jointly with Area D, which consumes it. Leaving it completely
    unconstrained means ``"terraform patch!!"`` and ``"<script>x</script>"`` are valid
    Rule content, and the value is inside the approval semantic hash, so junk there
    permanently churns approval bindings. Fixing the shape now costs nothing and does
    not pre-empt the vocabulary decision.
    """
    value = _text(value, name)
    if not TOKEN_PATTERN.fullmatch(value):
        raise ContractValidationError(f"{name} must be an UPPER_SNAKE_CASE token")
    return value


def _rule_id(value: Any) -> str:
    value = _text(value, "rule_id")
    if not RULE_ID_PATTERN.fullmatch(value):
        raise ContractValidationError("rule_id does not follow docs/NAMING.md")
    return value


def _enum(enum_type: type[Enum], value: Any, name: str):
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ContractValidationError(f"{name} must be one of: {allowed}") from exc


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_enum_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _enum_value(item) for key, item in value.items()}
    return value


class Contract:
    def to_dict(self) -> dict[str, Any]:
        return _enum_value(asdict(self))


@dataclass(frozen=True)
class Control(Contract):
    control_key: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Control:
        value = _mapping(value, "control", frozenset({"control_key"}))
        return cls(control_key=_text(value.get("control_key"), "control_key"))


@dataclass(frozen=True)
class SourceReference(Contract):
    document_id: str
    document_version: str
    section: str
    content_hash: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SourceReference:
        value = _mapping(
            value,
            "source_reference",
            frozenset({"content_hash", "document_id", "document_version", "section"}),
        )
        return cls(
            document_id=_text(value.get("document_id"), "document_id"),
            document_version=_text(value.get("document_version"), "document_version"),
            section=_text(value.get("section"), "section"),
            content_hash=_hash(value.get("content_hash"), "content_hash"),
        )

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return (self.document_id, self.document_version, self.section, self.content_hash)


@dataclass(frozen=True)
class PolicySource(Contract):
    source_id: str
    source_type: SourceType
    source_version: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PolicySource:
        value = _mapping(
            value, "policy_source", frozenset({"source_id", "source_type", "source_version"})
        )
        return cls(
            source_id=_text(value.get("source_id"), "source_id"),
            source_type=_enum(SourceType, value.get("source_type"), "source_type"),
            source_version=_text(value.get("source_version"), "source_version"),
        )


@dataclass(frozen=True)
class SourceControlMapping(Contract):
    source_reference: SourceReference
    resource_type: str
    control_key: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SourceControlMapping:
        value = _mapping(
            value,
            "source_control_mapping",
            frozenset({"control_key", "resource_type", "source_reference"}),
        )
        return cls(
            source_reference=SourceReference.from_dict(value.get("source_reference")),
            resource_type=_text(value.get("resource_type"), "resource_type"),
            control_key=_text(value.get("control_key"), "control_key"),
        )


@dataclass(frozen=True)
class Rule(Contract):
    rule_id: str
    version: int
    status: RuleStatus
    source_type: SourceType
    source_references: tuple[SourceReference, ...]
    resource_type: str
    control_key: str
    evaluation_type: EvaluationType
    severity: Severity
    requirement: str
    remediation_type: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Rule:
        value = _mapping(
            value,
            "rule",
            frozenset(
                {
                    "control_key",
                    "evaluation_type",
                    "remediation_type",
                    "requirement",
                    "resource_type",
                    "rule_id",
                    "severity",
                    "source_references",
                    "source_type",
                    "status",
                    "version",
                }
            ),
        )
        rule_id = _rule_id(value.get("rule_id"))
        raw_references = value.get("source_references")
        if (
            not isinstance(raw_references, Sequence)
            or isinstance(raw_references, (str, bytes))
            or not raw_references
        ):
            raise ContractValidationError("source_references must be a non-empty array")
        references = tuple(SourceReference.from_dict(item) for item in raw_references)
        if len({item.identity for item in references}) != len(references):
            raise ContractValidationError("source_references must not contain duplicates")
        return cls(
            rule_id=rule_id,
            version=_positive_int(value.get("version"), "version"),
            status=_enum(RuleStatus, value.get("status"), "status"),
            source_type=_enum(SourceType, value.get("source_type"), "source_type"),
            source_references=references,
            resource_type=_text(value.get("resource_type"), "resource_type"),
            control_key=_text(value.get("control_key"), "control_key"),
            evaluation_type=_enum(EvaluationType, value.get("evaluation_type"), "evaluation_type"),
            severity=_enum(Severity, value.get("severity"), "severity"),
            requirement=_text(value.get("requirement"), "requirement"),
            remediation_type=_token(value.get("remediation_type"), "remediation_type"),
        )

    @property
    def identity(self) -> tuple[str, int]:
        return (self.rule_id, self.version)


@dataclass(frozen=True)
class RuleApproval(Contract):
    rule_id: str
    version: int
    rule_content_hash: str
    approved_by: str
    approved_at: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> RuleApproval:
        value = _mapping(
            value,
            "rule_approval",
            frozenset({"approved_at", "approved_by", "rule_content_hash", "rule_id", "version"}),
        )
        return cls(
            rule_id=_rule_id(value.get("rule_id")),
            version=_positive_int(value.get("version"), "version"),
            rule_content_hash=_hash(value.get("rule_content_hash"), "rule_content_hash"),
            approved_by=_text(value.get("approved_by"), "approved_by"),
            approved_at=_text(value.get("approved_at"), "approved_at"),
        )

    @property
    def identity(self) -> tuple[str, int]:
        return (self.rule_id, self.version)


@dataclass(frozen=True)
class RulePin(Contract):
    rule_id: str
    version: int

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> RulePin:
        value = _mapping(value, "rule_pin", frozenset({"rule_id", "version"}))
        return cls(
            rule_id=_rule_id(value.get("rule_id")),
            version=_positive_int(value.get("version"), "version"),
        )

    @property
    def identity(self) -> tuple[str, int]:
        return (self.rule_id, self.version)


@dataclass(frozen=True)
class PolicyProfile(Contract):
    policy_profile_id: str
    policy_profile_version: int
    rule_pins: tuple[RulePin, ...]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PolicyProfile:
        value = _mapping(
            value,
            "policy_profile",
            frozenset({"policy_profile_id", "policy_profile_version", "rule_pins"}),
        )
        raw_pins = value.get("rule_pins")
        if not isinstance(raw_pins, Sequence) or isinstance(raw_pins, (str, bytes)) or not raw_pins:
            raise ContractValidationError("rule_pins must be a non-empty array")
        pins = tuple(RulePin.from_dict(item) for item in raw_pins)
        if len({item.identity for item in pins}) != len(pins):
            raise ContractValidationError("rule_pins must not contain duplicates")
        return cls(
            policy_profile_id=_text(value.get("policy_profile_id"), "policy_profile_id"),
            policy_profile_version=_positive_int(
                value.get("policy_profile_version"), "policy_profile_version"
            ),
            rule_pins=pins,
        )

    @property
    def identity(self) -> tuple[str, int]:
        return (self.policy_profile_id, self.policy_profile_version)


@dataclass(frozen=True)
class AdminSettingsSnapshotReference(Contract):
    admin_settings_snapshot_hash: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AdminSettingsSnapshotReference:
        value = _mapping(
            value, "admin_settings_snapshot_reference", frozenset({"admin_settings_snapshot_hash"})
        )
        return cls(
            admin_settings_snapshot_hash=_hash(
                value.get("admin_settings_snapshot_hash"), "admin_settings_snapshot_hash"
            )
        )


@dataclass(frozen=True)
class EffectiveRuleSet(Contract):
    policy_profile_id: str
    policy_profile_version: int
    phase: RuleSetPhase
    admin_settings_snapshot_hash: str
    rules: tuple[Rule, ...]
    rule_set_hash: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> EffectiveRuleSet:
        value = _mapping(
            value,
            "effective_rule_set",
            frozenset(
                {
                    "admin_settings_snapshot_hash",
                    "phase",
                    "policy_profile_id",
                    "policy_profile_version",
                    "rule_set_hash",
                    "rules",
                }
            ),
        )
        raw_rules = value.get("rules")
        if not isinstance(raw_rules, Sequence) or isinstance(raw_rules, (str, bytes)):
            raise ContractValidationError("effective rules must be an array")
        return cls(
            policy_profile_id=_text(value.get("policy_profile_id"), "policy_profile_id"),
            policy_profile_version=_positive_int(
                value.get("policy_profile_version"), "policy_profile_version"
            ),
            phase=_enum(RuleSetPhase, value.get("phase"), "phase"),
            admin_settings_snapshot_hash=_hash(
                value.get("admin_settings_snapshot_hash"), "admin_settings_snapshot_hash"
            ),
            rules=tuple(Rule.from_dict(item) for item in raw_rules),
            rule_set_hash=_hash(value.get("rule_set_hash"), "rule_set_hash"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_profile_id": self.policy_profile_id,
            "policy_profile_version": self.policy_profile_version,
            "phase": self.phase.value,
            "admin_settings_snapshot_hash": self.admin_settings_snapshot_hash,
            "rules": [item.to_dict() for item in self.rules],
            "rule_set_hash": self.rule_set_hash,
        }


@dataclass(frozen=True)
class PolicyEvidence(Contract):
    evidence_id: str
    source_reference: SourceReference
    locator: str
    excerpt: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PolicyEvidence:
        value = _mapping(
            value,
            "policy_evidence",
            frozenset({"evidence_id", "excerpt", "locator", "source_reference"}),
        )
        return cls(
            evidence_id=_text(value.get("evidence_id"), "evidence_id"),
            source_reference=SourceReference.from_dict(value.get("source_reference")),
            locator=_text(value.get("locator"), "locator"),
            excerpt=_text(value.get("excerpt"), "excerpt"),
        )


@dataclass(frozen=True)
class PolicyQuestion(Contract):
    question: str
    allowed_source_ids: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PolicyQuestion:
        value = _mapping(value, "policy_question", frozenset({"allowed_source_ids", "question"}))
        raw_sources = value.get("allowed_source_ids")
        if (
            not isinstance(raw_sources, Sequence)
            or isinstance(raw_sources, (str, bytes))
            or not raw_sources
        ):
            raise ContractValidationError("allowed_source_ids must be a non-empty array")
        sources = tuple(_text(item, "allowed_source_id") for item in raw_sources)
        if len(set(sources)) != len(sources):
            raise ContractValidationError("allowed_source_ids must not contain duplicates")
        return cls(
            question=_text(value.get("question"), "question"),
            allowed_source_ids=sources,
        )


@dataclass(frozen=True)
class PolicyAnswer(Contract):
    answer: str
    evidence: tuple[PolicyEvidence, ...]
    limitations: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PolicyAnswer:
        value = _mapping(value, "policy_answer", frozenset({"answer", "evidence", "limitations"}))
        raw_evidence = value.get("evidence", ())
        raw_limitations = value.get("limitations", ())
        if not isinstance(raw_evidence, Sequence) or isinstance(raw_evidence, (str, bytes)):
            raise ContractValidationError("evidence must be an array")
        if not isinstance(raw_limitations, Sequence) or isinstance(raw_limitations, (str, bytes)):
            raise ContractValidationError("limitations must be an array")
        return cls(
            answer=_text(value.get("answer"), "answer"),
            evidence=tuple(PolicyEvidence.from_dict(item) for item in raw_evidence),
            limitations=tuple(_text(item, "limitation") for item in raw_limitations),
        )


@dataclass(frozen=True)
class EvidenceQueryResult(Contract):
    status: EvidenceResultStatus
    evidence: tuple[PolicyEvidence, ...]
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.status is EvidenceResultStatus.FOUND and not self.evidence:
            raise ContractValidationError("FOUND evidence result must contain evidence")
        if self.status is EvidenceResultStatus.NOT_FOUND and (self.evidence or self.error_code):
            raise ContractValidationError("NOT_FOUND must not contain evidence or error_code")
        if self.status is EvidenceResultStatus.ERROR and not self.error_code:
            raise ContractValidationError("ERROR evidence result requires error_code")


@dataclass(frozen=True)
class RuleEvaluationMetric(Contract):
    resource_id: str
    rule_id: str
    rule_version: int
    source_id: str
    source_type: SourceType
    severity: Severity
    evaluation_status: EvaluationStatus | None
    execution_status: ExecutionStatus

    @property
    def identity(self) -> tuple[str, str, int, str]:
        """Existing fields that identify one Resource × Rule × Source metric."""
        return (self.resource_id, self.rule_id, self.rule_version, self.source_id)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> RuleEvaluationMetric:
        value = _mapping(
            value,
            "rule_evaluation_metric",
            frozenset(
                {
                    "evaluation_status",
                    "execution_status",
                    "resource_id",
                    "rule_id",
                    "rule_version",
                    "severity",
                    "source_id",
                    "source_type",
                }
            ),
        )
        execution_status = _enum(ExecutionStatus, value.get("execution_status"), "execution_status")
        raw_status = value.get("evaluation_status")
        evaluation_status = (
            None if raw_status is None else _enum(EvaluationStatus, raw_status, "evaluation_status")
        )
        if execution_status is ExecutionStatus.ERROR and evaluation_status is not None:
            raise ContractValidationError("execution ERROR must have null evaluation_status")
        if execution_status is ExecutionStatus.SUCCESS and evaluation_status is None:
            raise ContractValidationError("execution SUCCESS requires evaluation_status")
        return cls(
            resource_id=_text(value.get("resource_id"), "resource_id"),
            rule_id=_rule_id(value.get("rule_id")),
            rule_version=_positive_int(value.get("rule_version"), "rule_version"),
            source_id=_text(value.get("source_id"), "source_id"),
            source_type=_enum(SourceType, value.get("source_type"), "source_type"),
            severity=_enum(Severity, value.get("severity"), "severity"),
            evaluation_status=evaluation_status,
            execution_status=execution_status,
        )


# Scoring version 어휘.
#
# 값의 정본은 알고리즘을 구현하는 Domain이 아니라 Contract 계층이다. Consumer(A의 start
# protocol, C의 metric 생성)가 Domain 코드를 import하지 않고도 값을 검증할 수 있어야 하기
# 때문이다. 알고리즘 자체는 계속 packages/governance/scoring/이 소유한다.
#
# `SCORING_VERSION`은 새 Assessment에 부여할 현재 version이고,
# `SUPPORTED_SCORING_VERSIONS`는 이 build가 계산할 수 있는 version 집합이다. 과거
# Assessment 재현 때문에 두 값은 같지 않을 수 있다.
#
# version 추가 규칙은 docs/CONTRACTS.md의 SourceScoreCoverage 절을 따른다.
SCORING_VERSION = "1"
SUPPORTED_SCORING_VERSIONS = frozenset({SCORING_VERSION})


def require_supported_scoring_version(value: Any, name: str = "scoring_version") -> str:
    """Reject a scoring version this build cannot compute.

    Pinning an unknown version at Assessment start would run the whole evaluation and
    only fail at scoring time, far from the cause. Consumers validate here instead.
    """
    value = _text(value, name)
    if not SCORING_VERSION_PATTERN.fullmatch(value):
        raise ContractValidationError(f"{name} must be a decimal integer string")
    if value not in SUPPORTED_SCORING_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_SCORING_VERSIONS))
        raise ContractValidationError(f"unsupported {name}: {value}; supported: {supported}")
    return value


@dataclass(frozen=True)
class SourceScoreCoverage(Contract):
    source_id: str
    source_type: SourceType
    scoring_version: str
    score: float | None
    coverage: float | None
    pass_count: int
    fail_count: int
    manual_review_count: int
    not_applicable_count: int
    execution_error_count: int
