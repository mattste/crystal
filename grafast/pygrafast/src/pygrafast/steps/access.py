"""AccessStep - extract a property from a step's result by path."""

from __future__ import annotations

from typing import Any, Sequence

from ..step import ExecutionDetails, Step, UnbatchedStep


class AccessStep(UnbatchedStep[Any]):
    """Extracts a nested property from a step's result."""

    is_sync_and_safe = True

    def __init__(self, parent: Step[Any], path: Sequence[str]) -> None:
        super().__init__()
        self._path = list(path)
        self._dep_id = self.add_dependency(parent)

    def to_string_meta(self) -> str | None:
        return ".".join(self._path)

    def unbatched_execute(self, value: Any) -> Any:
        result = value
        for key in self._path:
            if result is None:
                return None
            if isinstance(result, dict):
                result = result.get(key)
            else:
                result = getattr(result, key, None)
        return result


def access(step: Step[Any], path: str | Sequence[str]) -> AccessStep:
    """Create an AccessStep for property access."""
    if isinstance(path, str):
        path = [path]
    return AccessStep(step, path)
