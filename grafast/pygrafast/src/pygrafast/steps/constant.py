"""ConstantStep - wraps a static value."""

from __future__ import annotations

from typing import Any, TypeVar

from ..step import ExecutionDetails, UnbatchedStep

TData = TypeVar("TData")


class ConstantStep(UnbatchedStep[TData]):
    """A step that always returns the same constant value."""

    is_sync_and_safe = True

    def __init__(self, data: TData) -> None:
        super().__init__()
        self.data = data
        t = type(data)
        if data is None or isinstance(data, (bool, int, float, str)):
            self.peer_key = f"{t.__name__}|{data}"

    def to_string_meta(self) -> str | None:
        return repr(self.data)

    def unbatched_execute(self) -> TData:
        return self.data

    def execute(self, details: ExecutionDetails) -> list[TData]:
        return [self.data] * details.count

    def eval(self) -> TData:
        return self.data

    def eval_is(self, value: Any) -> bool:
        return self.data is value or self.data == value


def constant(data: Any) -> ConstantStep[Any]:
    """Create a ConstantStep wrapping the given value."""
    return ConstantStep(data)
