"""StepTracker - manages step registration and dependency tracking."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..step import Step


class StepTracker:
    """Tracks all steps in an operation plan."""

    _steps: list[Step[Any]]

    def __init__(self) -> None:
        self._steps = []

    @property
    def step_count(self) -> int:
        return len(self._steps)

    def add_step(self, step: Step[Any]) -> int:
        """Register a step and return its unique id."""
        step_id = len(self._steps)
        self._steps.append(step)
        return step_id

    def get_step_by_id(self, step_id: int) -> Step[Any]:
        """Get a step by its id."""
        return self._steps[step_id]

    def all_steps(self) -> list[Step[Any]]:
        """Return all registered steps."""
        return list(self._steps)
