"""Phase 04 Package B: time-watermarked goal tracking
(FINAL_HUMANOID_BRAIN_ARCHITECTURE.md Section 19).

A `GoalRecord` is a durable commitment (a user task, a self-directed
follow-up) with an optional deadline. `review_due_goals` is the
`DUE_GOAL_REVIEW` background job's core logic: it never runs on a clock of
its own, it only compares each active goal's deadline against whatever
watermark the caller (the background scheduler) supplies.
"""

from __future__ import annotations

import time

from pydantic import BaseModel, Field


class GoalRecord(BaseModel):
    """One tracked goal, active until completed, expired, or failed."""

    goal_id: str
    type: str = "user_task"
    source: str = "user"
    description: str
    owner: str = "user"
    created_at: float = Field(default_factory=time.time)
    priority_class: int = 50
    deadline: float | None = None
    success_test: str | None = None
    status: str = "ACTIVE"
    last_progress: float = 0.0
    uncertainty: float = 0.0


def review_due_goals(
    goals: list[GoalRecord], current_watermark: float
) -> tuple[list[GoalRecord], list[str]]:
    """Expire any ACTIVE goal whose deadline has passed the watermark.

    Mutates and returns the same `GoalRecord` instances (status flips
    in place) alongside a human-readable note per expiry -- goals with no
    deadline, or a deadline still ahead of `current_watermark`, are left
    untouched.
    """
    notes: list[str] = []
    for goal in goals:
        if goal.status != "ACTIVE":
            continue
        if goal.deadline is not None and current_watermark >= goal.deadline:
            goal.status = "EXPIRED"
            notes.append(
                f"Goal '{goal.goal_id}' ({goal.description}) expired: "
                f"deadline {goal.deadline:.2f} reached at watermark "
                f"{current_watermark:.2f}."
            )
    return goals, notes
