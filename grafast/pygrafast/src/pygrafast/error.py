"""Error types and flag-based error handling."""

from __future__ import annotations

from typing import Any

from .constants import ExecutionEntryFlags, FLAG_ERROR, FLAG_INHIBITED, FLAG_NULL


class FlaggedValue:
    """Wraps a value with a flag indicating error/null/inhibited status."""

    __slots__ = ("flag", "value")

    def __init__(self, flag: ExecutionEntryFlags, value: Any) -> None:
        self.flag = flag
        self.value = value

    def __repr__(self) -> str:
        return f"FlaggedValue(flag={self.flag}, value={self.value!r})"


class SafeError(Exception):
    """An error that is safe to expose to the end user."""

    pass


def flag_error(error: Exception) -> FlaggedValue:
    """Wrap an error as a FlaggedValue with FLAG_ERROR."""
    return FlaggedValue(FLAG_ERROR, error)


def flag_null() -> FlaggedValue:
    """Create a FlaggedValue representing null."""
    return FlaggedValue(FLAG_NULL, None)


def flag_inhibited() -> FlaggedValue:
    """Create a FlaggedValue representing an inhibited value."""
    return FlaggedValue(FLAG_INHIBITED, None)


def is_flagged_value(value: Any) -> bool:
    """Check if a value is a FlaggedValue."""
    return isinstance(value, FlaggedValue)
