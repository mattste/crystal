"""InputStaticLeafStep - represents a literal scalar/enum argument value."""

from __future__ import annotations

from typing import Any

from ..step import UnbatchedStep


class InputStaticLeafStep(UnbatchedStep[Any]):
    """A step that returns a constant input value (literal in the query)."""

    is_sync_and_safe = True

    def __init__(self, value: Any) -> None:
        super().__init__()
        self._value = value

    def to_string_meta(self) -> str | None:
        return repr(self._value)

    def unbatched_execute(self) -> Any:
        return self._value

    def execute(self, details: Any) -> list[Any]:
        return [self._value] * details.count
