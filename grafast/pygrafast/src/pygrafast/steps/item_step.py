"""ItemStep - represents an individual item within a list iteration."""

from __future__ import annotations

from typing import Any

from ..step import Step


class ItemStep(Step[Any]):
    """Represents an individual item from a list.

    This step's values are injected by the parent EachStep during execution.
    It never executes on its own.
    """

    _no_exec = True
    is_sync_and_safe = True

    def __init__(self, parent_list_step: Step[Any]) -> None:
        super().__init__()
        self._parent_list_step = parent_list_step
        self._is_unary = False  # One value per list item

    def to_string_meta(self) -> str | None:
        return f"item of {self._parent_list_step}"
