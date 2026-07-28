from enum import StrEnum


class BlockCategory(StrEnum):
    WAKE = "wake"
    SLEEP = "sleep"
    COMMUTE = "commute"
    CLASS = "class"
    WORK = "work"
    STUDY = "study"
    MEAL = "meal"
    WORKOUT = "workout"
    CHORE = "chore"
    APPOINTMENT = "appointment"
    FREE_TIME = "free_time"
    CUSTOM = "custom"


class Flexibility(StrEnum):
    FIXED = "fixed"
    FLEXIBLE = "flexible"
    OPTIONAL = "optional"


class TrackingStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    MISSED = "missed"


class ImportMode(StrEnum):
    REPLACE_SCOPE = "replace_scope"
    PATCH = "patch"


class DraftStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    APPLIED = "applied"
    REJECTED = "rejected"


class ChangeOperation(StrEnum):
    ADD = "add"
    UPDATE = "update"
    CANCEL = "cancel"


class ImportEntityType(StrEnum):
    SEMESTER = "semester"
    TEMPLATE = "template"
    OCCURRENCE = "occurrence"


class IssueSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class AssignmentInboxStatus(StrEnum):
    INBOX = "inbox"
    PLANNED = "planned"
    COMPLETED = "completed"
    IGNORED = "ignored"
    STALE = "stale"
    CANCELED = "canceled"


class ExternalRecordState(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    CANCELED = "canceled"


class DuePrecision(StrEnum):
    DATE = "date"
    DATETIME = "datetime"


class SyncStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class SyncConflictStatus(StrEnum):
    OPEN = "open"
    KEEP_PLANNER = "keep_planner"
    USE_REMOTE = "use_remote"


class SyncConnector(StrEnum):
    GOOGLE = "google"
    BLACKBOARD = "blackboard"
