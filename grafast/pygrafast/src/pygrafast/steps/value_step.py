"""ValueStep - holds a unary value like context or rootValue. Never executes."""

from __future__ import annotations

from typing import Any, TypeVar

from ..step import Step

TData = TypeVar("TData")


class ValueStep(Step[TData]):
    """A step representing a unary value (context, rootValue, etc).

    This step never executes - its value is set directly in the bucket store
    at execution time.
    """

    _no_exec = True
    is_sync_and_safe = True

    def __init__(self) -> None:
        super().__init__()
        self._is_unary = True

    def to_string_meta(self) -> str | None:
        return "unary"
