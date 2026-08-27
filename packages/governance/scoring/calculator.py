"""Source-partitioned deterministic score and coverage calculation.

Weights come from the Effective Rule Set, never from the consumer payload:
docs/CONTRACTS.md fixes the weight to ``Effective Rule.severity`` before any
verdict exists, so a metric that disagrees with its pinned Rule is rejected
rather than silently reweighted.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from packages.contracts.governance import (
    EffectiveRuleSet,
    EvaluationStatus,
    ExecutionStatus,
    Rule,
    RuleEvaluationMetric,
    Severity,
    SourceScoreCoverage,
    SourceType,
)

from ..errors import GovernanceValidationError

SCORING_VERSION = "1"
SUPPORTED_SCORING_VERSIONS = frozenset({SCORING_VERSION})
SEVERITY_WEIGHTS = {
    Severity.CRITICAL: 10,
    Severity.HIGH: 5,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
}


def _percent(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator * 100.0 / denominator, 1)


def _pinned_rule(evaluation: RuleEvaluationMetric, index: dict[tuple[str, int], Rule]) -> Rule:
    """Bind one metric to its Effective Rule, rejecting any consumer disagreement."""
    identity = (evaluation.rule_id, evaluation.rule_version)
    rule = index.get(identity)
    if rule is None:
        raise GovernanceValidationError(
            f"evaluation references a rule outside the Effective Rule Set: "
            f"{evaluation.rule_id}@{evaluation.rule_version}"
        )
    if evaluation.severity is not rule.severity:
        raise GovernanceValidationError(
            f"evaluation severity does not match the Effective Rule: "
            f"{evaluation.rule_id}@{evaluation.rule_version}"
        )
    if evaluation.source_type is not rule.source_type:
        raise GovernanceValidationError(
            f"evaluation source_type does not match the Effective Rule: "
            f"{evaluation.rule_id}@{evaluation.rule_version}"
        )
    if evaluation.source_id not in {reference.document_id for reference in rule.source_references}:
        raise GovernanceValidationError(
            f"evaluation source_id is not a validated Source Reference of "
            f"{evaluation.rule_id}@{evaluation.rule_version}"
        )
    return rule


def calculate_source_metrics(
    evaluations: Iterable[RuleEvaluationMetric],
    effective_rule_set: EffectiveRuleSet,
    *,
    scoring_version: str = SCORING_VERSION,
) -> tuple[SourceScoreCoverage, ...]:
    if scoring_version not in SUPPORTED_SCORING_VERSIONS:
        raise GovernanceValidationError(f"unsupported scoring_version: {scoring_version}")
    index = {rule.identity: rule for rule in effective_rule_set.rules}

    partitions: dict[tuple[str, SourceType], list[tuple[RuleEvaluationMetric, Rule]]] = defaultdict(
        list
    )
    seen_metrics: set[tuple[str, str, int, str]] = set()
    for evaluation in evaluations:
        if evaluation.identity in seen_metrics:
            raise GovernanceValidationError(
                "duplicate Resource x Rule x Source metric: "
                f"{evaluation.resource_id}|{evaluation.rule_id}@"
                f"{evaluation.rule_version}|{evaluation.source_id}"
            )
        seen_metrics.add(evaluation.identity)
        rule = _pinned_rule(evaluation, index)
        partitions[(evaluation.source_id, rule.source_type)].append((evaluation, rule))

    results: list[SourceScoreCoverage] = []
    for (source_id, source_type), items in sorted(
        partitions.items(), key=lambda item: (item[0][0], item[0][1].value)
    ):
        counts = {status: 0 for status in EvaluationStatus}
        execution_errors = 0
        passed_weight = 0
        decided_weight = 0
        for evaluation, rule in items:
            if evaluation.execution_status is ExecutionStatus.ERROR:
                execution_errors += 1
                continue
            if evaluation.evaluation_status is None:
                raise GovernanceValidationError(
                    "successful execution requires an evaluation_status"
                )
            counts[evaluation.evaluation_status] += 1
            if evaluation.evaluation_status in {EvaluationStatus.PASS, EvaluationStatus.FAIL}:
                weight = SEVERITY_WEIGHTS[rule.severity]
                decided_weight += weight
                if evaluation.evaluation_status is EvaluationStatus.PASS:
                    passed_weight += weight
        decided_count = counts[EvaluationStatus.PASS] + counts[EvaluationStatus.FAIL]
        coverage_denominator = decided_count + counts[EvaluationStatus.MANUAL_REVIEW]
        results.append(
            SourceScoreCoverage(
                source_id=source_id,
                source_type=source_type,
                scoring_version=scoring_version,
                score=_percent(passed_weight, decided_weight),
                coverage=_percent(decided_count, coverage_denominator),
                pass_count=counts[EvaluationStatus.PASS],
                fail_count=counts[EvaluationStatus.FAIL],
                manual_review_count=counts[EvaluationStatus.MANUAL_REVIEW],
                not_applicable_count=counts[EvaluationStatus.NOT_APPLICABLE],
                execution_error_count=execution_errors,
            )
        )
    return tuple(results)
