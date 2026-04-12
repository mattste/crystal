"""TrackedValueStep - represents a runtime value from variables/context."""

from __future__ import annotations

from typing import Any

from ..step import ExecutionDetails, Step


class TrackedValueStep(Step[Any]):
    """Tracks a runtime variable value.

    During planning, we know the variable path but not its value.
    During execution, the value comes from the variable_values.
    """

    is_sync_and_safe = True
    _no_exec = True  # Value is injected into bucket store, not executed

    def __init__(self, path: list[str] | None = None) -> None:
        super().__init__()
        self._path = path or []
        self._is_unary = True

    def to_string_meta(self) -> str | None:
        if self._path:
            return ".".join(self._path)
        return "root"

    def get(self, key: str) -> TrackedValueStep:
        """Create a child TrackedValueStep for a subpath."""
        child = TrackedValueStep(self._path + [key])
        child.add_dependency(self)
        return child
