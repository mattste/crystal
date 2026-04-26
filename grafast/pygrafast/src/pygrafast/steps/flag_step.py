"""FlagStep - trap errors, nulls, and inhibited values.

Implements trap(), assert_not_null(), and inhibit_on_null() which correspond
to the TypeScript grafast __FlagStep, assertNotNull, inhibitOnNull, and trap.
"""

from __future__ import annotations

from typing import Any, Literal

from ..constants import (
    ALL_FLAGS,
    DEFAULT_FORBIDDEN_FLAGS,
    FLAG_ERROR,
    FLAG_INHIBITED,
    FLAG_NULL,
    TRAPPABLE_FLAGS,
    ExecutionEntryFlags,
    NO_FLAGS,
)
from ..error import FlaggedValue, SafeError, flag_error, flag_inhibited, is_flagged_value
from ..step import ExecutionDetails, Step

# Public trap flag constants
TRAP_ERROR = ExecutionEntryFlags(FLAG_ERROR)
TRAP_INHIBITED = ExecutionEntryFlags(FLAG_INHIBITED)
TRAP_ERROR_OR_INHIBITED = ExecutionEntryFlags(FLAG_ERROR | FLAG_INHIBITED)

# Default accept flags (allow null through by default)
DEFAULT_ACCEPT_FLAGS = ExecutionEntryFlags(FLAG_NULL)

TrapValue = Literal["NULL", "EMPTY_LIST", "PASS_THROUGH"]

_EMPTY_LIST: list[Any] = []


def _resolve_trap_value(tv: TrapValue) -> Any:
    """Convert a TrapValue string to the actual value to return."""
    if tv == "NULL":
        return None
    elif tv == "EMPTY_LIST":
        return _EMPTY_LIST
    elif tv == "PASS_THROUGH":
        return False  # sentinel meaning "pass the error/value through"
    else:
        raise ValueError(f"Unknown TrapValue: {tv!r}")


class FlagStep(Step[Any]):
    """Step that handles flag-based error/null/inhibited trapping.

    This is the Python equivalent of the TypeScript __FlagStep.
    """

    is_sync_and_safe = False

    def __init__(
        self,
        step: Step[Any],
        *,
        accept_flags: ExecutionEntryFlags = DEFAULT_ACCEPT_FLAGS,
        on_reject: Exception | None = None,
        value_for_inhibited: TrapValue = "PASS_THROUGH",
        value_for_error: TrapValue = "PASS_THROUGH",
    ) -> None:
        super().__init__()
        self._forbidden_flags = ExecutionEntryFlags(ALL_FLAGS & ~accept_flags)
        self._on_reject = on_reject
        self._value_for_inhibited = _resolve_trap_value(value_for_inhibited)
        self._value_for_error = _resolve_trap_value(value_for_error)

        # We always accept TRAPPABLE_FLAGS from the dependency so we can
        # inspect the flags ourselves
        self.add_dependency(step, accept_flags=TRAPPABLE_FLAGS)

    def to_string_meta(self) -> str | None:
        return f"dep={self.dependencies[0].id}"

    def _get_flags_for_dep(self, details: ExecutionDetails, index: int) -> ExecutionEntryFlags:
        """Get the flags for the dependency value at the given index.

        Checks both the bucket's flags array and the value itself.
        """
        value = details.values[0].at(index)
        if is_flagged_value(value):
            return value.flag

        # Check the bucket's flags for the dependency step
        bucket = details._bucket
        if bucket is not None:
            dep = self.dependencies[0]
            dep_id = dep.id
            if dep_id in bucket.flags:
                dep_flags = bucket.flags[dep_id]
                if isinstance(dep_flags, list) and index < len(dep_flags):
                    return dep_flags[index]

        # No explicit flag — null is FLAG_NULL, else NO_FLAGS
        if value is None:
            return FLAG_NULL
        return NO_FLAGS

    def execute(self, details: ExecutionDetails) -> list[Any]:
        results: list[Any] = []
        dep_ev = details.values[0]

        for i in range(details.count):
            value = dep_ev.at(i)
            flags = self._get_flags_for_dep(details, i)

            if flags != NO_FLAGS:
                disallowed = flags & self._forbidden_flags
                if disallowed:
                    # The value has flags that are forbidden by our configuration
                    if disallowed & FLAG_INHIBITED:
                        # Already inhibited, keep it
                        results.append(flag_inhibited())
                    elif disallowed & FLAG_ERROR:
                        # Error that's not trapped - propagate it
                        if is_flagged_value(value):
                            results.append(value)
                        else:
                            results.append(flag_error(Exception(str(value))))
                    elif disallowed & FLAG_NULL:
                        # Null that's not accepted - reject
                        if self._on_reject is not None:
                            results.append(flag_error(self._on_reject))
                        else:
                            results.append(flag_inhibited())
                    else:
                        # Other forbidden flags
                        if self._on_reject is not None:
                            results.append(flag_error(self._on_reject))
                        else:
                            results.append(flag_inhibited())
                else:
                    # The value has flags, but they are accepted (trapped)
                    if flags & FLAG_ERROR:
                        if self._value_for_error is not False:
                            # Trap the error: convert to the configured value
                            results.append(self._value_for_error)
                        else:
                            # PASS_THROUGH: convert error to its underlying value
                            err = value.value if is_flagged_value(value) else value
                            results.append(_error_to_object(err))
                    elif flags & FLAG_INHIBITED:
                        if self._value_for_inhibited is not False:
                            results.append(self._value_for_inhibited)
                        else:
                            results.append(None)
                    elif flags & FLAG_NULL:
                        # Null is accepted - pass through as None
                        results.append(None)
                    else:
                        results.append(value)
            else:
                # No flags, just pass the value through
                results.append(value)

        return results


class _ErrorObject:
    """Wraps an exception so its properties can be accessed like a dict
    or via attribute access.

    Used when trap(..., valueForError='PASS_THROUGH') converts an error
    into an object that can be queried for fields like `message`, `errcode`, etc.
    """

    def __init__(self, err: Exception) -> None:
        object.__setattr__(self, '_err', err)

    @property
    def message(self) -> str:
        return str(self._err)

    def __getattr__(self, key: str) -> Any:
        if key.startswith('_'):
            raise AttributeError(key)
        # Look for custom attributes on the exception
        err = object.__getattribute__(self, '_err')
        if hasattr(err, key):
            return getattr(err, key)
        return None

    def get(self, key: str, default: Any = None) -> Any:
        if key == "message":
            return str(self._err)
        # Look for custom attributes on the exception
        return getattr(self._err, key, default)

    def __getitem__(self, key: str) -> Any:
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def __contains__(self, key: str) -> bool:
        if key == "message":
            return True
        return hasattr(self._err, key)

    def __repr__(self) -> str:
        return f"_ErrorObject({self._err!r})"


def _error_to_object(err: Any) -> Any:
    """Convert an exception to an object with .message etc."""
    if isinstance(err, Exception):
        return _ErrorObject(err)
    return err


def trap(
    step: Step[Any],
    accept_flags: ExecutionEntryFlags,
    options: dict[str, Any] | None = None,
) -> FlagStep:
    """Trap errors/nulls/inhibited on a step.

    accept_flags: which flags to trap (e.g. TRAP_ERROR)
    options: dict with optional keys:
      - valueForError: "NULL" | "EMPTY_LIST" | "PASS_THROUGH"
      - valueForInhibited: "NULL" | "EMPTY_LIST" | "PASS_THROUGH"
    """
    opts = options or {}
    combined_flags = ExecutionEntryFlags((accept_flags & TRAPPABLE_FLAGS) | FLAG_NULL)
    return FlagStep(
        step,
        accept_flags=combined_flags,
        value_for_error=opts.get("valueForError", "PASS_THROUGH"),
        value_for_inhibited=opts.get("valueForInhibited", "PASS_THROUGH"),
    )


def assert_not_null(
    step: Step[Any],
    message: str,
) -> FlagStep:
    """Assert that a step's value is not null.

    If the value is null, raises a SafeError with the given message.
    This is equivalent to the TypeScript assertNotNull().
    """
    return FlagStep(
        step,
        accept_flags=ExecutionEntryFlags(DEFAULT_ACCEPT_FLAGS & ~FLAG_NULL),
        on_reject=SafeError(message),
    )


def inhibit_on_null(
    step: Step[Any],
) -> FlagStep:
    """Inhibit execution if the step's value is null.

    This is equivalent to the TypeScript inhibitOnNull().
    """
    return FlagStep(
        step,
        accept_flags=ExecutionEntryFlags(DEFAULT_ACCEPT_FLAGS & ~FLAG_NULL),
    )
