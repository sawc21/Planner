class SemesterOpsError(Exception):
    """Base class for expected application errors."""


class NotFoundError(SemesterOpsError):
    pass


class ValidationError(SemesterOpsError):
    pass


class IdempotencyConflictError(SemesterOpsError):
    pass


class DraftBlockedError(SemesterOpsError):
    pass


class StaleRevisionError(SemesterOpsError):
    pass
