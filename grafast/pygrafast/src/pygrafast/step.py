"""Step base classes - the core abstraction of pygrafast."""

from __future__ import annotations

from typing import Any, Generic, Sequence, TypeVar

from .constants import (
    ALL_FLAGS,
    DEFAULT_FORBIDDEN_FLAGS,
    TRAPPABLE_FLAGS,
    ExecutionEntryFlags,
    NO_FLAGS,
)
from .engine.with_global_layer_plan import (
    current_layer_plan,
    current_polymorphic_paths,
)

TData = TypeVar("TData")


class ExecutionDetails:
    """Details passed to Step.execute()."""

    __slots__ = ("count", "values", "_bucket")

    def __init__(
        self, count: int, values: list[ExecutionValue]
    ) -> None:
        self.count = count
        self.values = values
        self._bucket: Any = None


class ExecutionValue:
    """Wraps the values for a single dependency across the batch."""

    __slots__ = ("_entries", "_is_unary", "_unary_value")

    def __init__(
        self,
        entries: list[Any] | None = None,
        *,
        is_unary: bool = False,
        unary_value: Any = None,
    ) -> None:
        self._entries = entries
        self._is_unary = is_unary
        self._unary_value = unary_value

    @property
    def is_batch(self) -> bool:
        return not self._is_unary

    def at(self, index: int) -> Any:
        if self._is_unary:
            return self._unary_value
        assert self._entries is not None
        return self._entries[index]

    def get(self) -> Any:
        """For unary values, get the single value."""
        assert self._is_unary
        return self._unary_value


class Step(Generic[TData]):
    """Base class for all execution steps."""

    # Subclasses should set this
    _no_exec: bool = False
    is_sync_and_safe: bool = False
    has_side_effects: bool = False
    allow_multiple_optimizations: bool = False

    def __init__(self) -> None:
        from .engine.layer_plan import LayerPlan

        self.layer_plan = current_layer_plan()
        self.operation_plan = self.layer_plan.operation_plan
        self._is_unary: bool = True
        self.is_arguments_finalized: bool = False
        self.is_finalized: bool = False
        self.is_optimized: bool = False
        self.store: bool = True
        self.polymorphic_paths = current_polymorphic_paths()
        self.peer_key: str | None = None

        self._dependencies: list[Step[Any]] = []
        self._dependency_forbidden_flags: list[ExecutionEntryFlags] = []
        self._dependents: list[tuple[Step[Any], int]] = []

        # Register with layer plan (sets self.id)
        self.id: int = self.layer_plan._add_step(self)

    @property
    def dependencies(self) -> Sequence[Step[Any]]:
        return self._dependencies

    @property
    def dependency_count(self) -> int:
        return len(self._dependencies)

    def add_dependency(self, step: Step[Any], *, accept_flags: ExecutionEntryFlags | None = None) -> int:
        """Add a dependency on another step. Returns the dependency index."""
        dep_id = len(self._dependencies)
        self._dependencies.append(step)
        forbidden = DEFAULT_FORBIDDEN_FLAGS if accept_flags is None else ExecutionEntryFlags(ALL_FLAGS & ~accept_flags)
        self._dependency_forbidden_flags.append(forbidden)
        step._dependents.append((self, dep_id))

        # Track unary status
        if not step._is_unary:
            self._is_unary = False

        return dep_id

    # Alias for compatibility with TS naming
    def add_data_dependency(self, step: Step[Any]) -> int:
        """Add a data-only dependency."""
        return self.add_dependency(step)

    def get_dep(self, dep_id: int) -> Step[Any]:
        """Get a dependency step by index."""
        return self._dependencies[dep_id]

    def execute(self, details: ExecutionDetails) -> list[TData]:
        """Execute this step for a batch of entries. Must be overridden."""
        raise NotImplementedError(f"{type(self).__name__}.execute() not implemented")

    def finalize(self) -> None:
        """Called after planning to prepare for execution."""
        self.is_finalized = True

    def __repr__(self) -> str:
        meta = self.to_string_meta()
        if meta:
            return f"{type(self).__name__}[{self.id}]({meta})"
        return f"{type(self).__name__}[{self.id}]"

    def to_string_meta(self) -> str | None:
        return None


class UnbatchedStep(Step[TData]):
    """A step that implements unbatched_execute for simpler single-value logic."""

    is_sync_and_safe: bool = True

    def unbatched_execute(self, *dep_values: Any) -> TData:
        """Execute for a single entry. Override this instead of execute()."""
        raise NotImplementedError(
            f"{type(self).__name__}.unbatched_execute() not implemented"
        )

    def execute(self, details: ExecutionDetails) -> list[TData]:
        """Batched execute built from unbatched_execute."""
        results: list[TData] = []
        dep_count = self.dependency_count
        for i in range(details.count):
            args = [details.values[d].at(i) for d in range(dep_count)]
            results.append(self.unbatched_execute(*args))
        return results
