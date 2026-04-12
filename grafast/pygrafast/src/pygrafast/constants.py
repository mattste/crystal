"""Flags and sentinel symbols for pygrafast."""

from __future__ import annotations

from typing import NewType

# Execution entry flags (bitwise)
ExecutionEntryFlags = NewType("ExecutionEntryFlags", int)

NO_FLAGS = ExecutionEntryFlags(0)
FLAG_ERROR = ExecutionEntryFlags(1 << 0)  # 1
FLAG_NULL = ExecutionEntryFlags(1 << 1)  # 2
FLAG_INHIBITED = ExecutionEntryFlags(1 << 2)  # 4
FLAG_POLY_SKIPPED = ExecutionEntryFlags(1 << 3)  # 8
FLAG_STOPPED = ExecutionEntryFlags(1 << 4)  # 16

TRAPPABLE_FLAGS = ExecutionEntryFlags(FLAG_ERROR | FLAG_NULL | FLAG_INHIBITED)
ALL_FLAGS = ExecutionEntryFlags(
    FLAG_ERROR | FLAG_NULL | FLAG_INHIBITED | FLAG_POLY_SKIPPED | FLAG_STOPPED
)
DEFAULT_FORBIDDEN_FLAGS = ExecutionEntryFlags(ALL_FLAGS & ~FLAG_NULL)


# Sentinel for "undefined" (distinct from None which maps to JS null)
class _UndefinedType:
    _instance: _UndefinedType | None = None

    def __new__(cls) -> _UndefinedType:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNDEFINED"

    def __bool__(self) -> bool:
        return False


UNDEFINED = _UndefinedType()
