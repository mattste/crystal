"""ListStep - combines multiple steps into a list/tuple."""

from __future__ import annotations

from typing import Any, Sequence, TypeVar

from ..step import ExecutionDetails, Step, UnbatchedStep

TData = TypeVar("TData")


class ListStep(UnbatchedStep[list[Any]]):
    """Combines values from multiple dependency steps into a list."""

    is_sync_and_safe = True

    def __init__(self, steps: Sequence[Step[Any]]) -> None:
        super().__init__()
        self._dep_ids: list[int] = []
        for step in steps:
            dep_id = self.add_dependency(step)
            self._dep_ids.append(dep_id)

    def to_string_meta(self) -> str | None:
        return f"{len(self._dep_ids)} items"

    def unbatched_execute(self, *values: Any) -> list[Any]:
        return list(values)

    def execute(self, details: ExecutionDetails) -> list[list[Any]]:
        results: list[list[Any]] = []
        n_deps = len(self._dep_ids)
        for i in range(details.count):
            row = [details.values[d].at(i) for d in range(n_deps)]
            results.append(row)
        return results


def list_(steps: Sequence[Step[Any]]) -> ListStep:
    """Create a ListStep combining the given steps."""
    return ListStep(steps)
