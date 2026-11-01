"""Stable error types for the finance tool layer (TOOL_CONTRACT §3)."""


class FinanceError(Exception):
    """Base error carrying a stable machine-readable code."""

    code = "internal_error"
    retryable = False

    def __init__(self, message: str = ""):
        super().__init__(message or self.code)
        self.message = message or self.code


class ValidationFailed(FinanceError):
    code = "validation_error"


class Unauthorized(FinanceError):
    code = "unauthorized"


class NotFound(FinanceError):
    code = "not_found"


class TemporarilyUnavailable(FinanceError):
    code = "temporarily_unavailable"
    retryable = True


class OutcomeUnknown(FinanceError):
    """A write may or may not have landed; caller must re-check by key."""

    code = "outcome_unconfirmed"
    retryable = True
