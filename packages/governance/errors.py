"""Stable Governance domain errors."""


class GovernanceError(ValueError):
    code = "GOVERNANCE_ERROR"


class GovernanceValidationError(GovernanceError):
    code = "VALIDATION_ERROR"


class GovernanceConflictError(GovernanceError):
    code = "CONFLICT"


class GovernanceNotFoundError(GovernanceError):
    code = "NOT_FOUND"
