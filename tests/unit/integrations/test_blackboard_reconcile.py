from datetime import UTC, date, datetime

from semester_ops.integrations.blackboard import (
    BlackboardFeedItem,
    ExistingBlackboardAssignment,
    planning_deadline,
    reconcile_blackboard_feed,
)


def item(
    uid: str,
    *,
    sequence: int = 0,
    title: str = "Assignment",
    status: str = "active",
) -> BlackboardFeedItem:
    return BlackboardFeedItem(
        uid=uid,
        recurrence_id=None,
        title=title,
        due=date(2026, 8, 24) if status == "active" else None,
        due_precision="date" if status == "active" else None,
        course_name="CS 101",
        description=None,
        url=None,
        status=status,  # type: ignore[arg-type]
        sequence=sequence,
        dtstamp=datetime(2026, 7, 28, tzinfo=UTC),
        last_modified=None,
    )


def test_reconcile_updates_cancels_and_marks_unexplained_absence_stale() -> None:
    existing = (
        ExistingBlackboardAssignment(item("changed", sequence=1)),
        ExistingBlackboardAssignment(item("canceled", sequence=1)),
        ExistingBlackboardAssignment(item("missing")),
        ExistingBlackboardAssignment(item("already-stale"), source_state="stale"),
    )
    incoming = (
        item("changed", sequence=2, title="Updated"),
        item("canceled", sequence=2, status="cancelled"),
        item("unknown-cancel", status="cancelled"),
    )

    result = reconcile_blackboard_feed(incoming, existing)

    assert [value.uid for value in result.upserts] == ["changed"]
    assert result.canceled == (("canceled", None),)
    assert result.stale == (("missing", None),)
    assert ("already-stale", None) in result.unchanged
    assert result.unknown_cancellations == (("unknown-cancel", None),)


def test_older_source_revision_cannot_overwrite_newer_assignment() -> None:
    current = ExistingBlackboardAssignment(item("assignment", sequence=4, title="Current"))
    result = reconcile_blackboard_feed(
        (item("assignment", sequence=3, title="Old value"),),
        (current,),
    )

    assert not result.upserts
    assert result.unchanged == (("assignment", None),)


def test_date_only_deadline_is_1159_pm_central_for_planning() -> None:
    deadline = planning_deadline(item("assignment"), timezone_name="America/Chicago")

    assert deadline.isoformat() == "2026-08-24T23:59:00-05:00"
