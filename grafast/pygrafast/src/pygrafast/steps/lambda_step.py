"""LambdaStep - applies a function to dependency values."""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from ..step import ExecutionDetails, Step, UnbatchedStep

TIn = TypeVar("TIn")
TOut = TypeVar("TOut")


class LambdaStep(UnbatchedStep[TOut]):
    """Calls a function for each entry, passing the dependency value."""

    is_sync_and_safe = False  # conservative default

    def __init__(
        self,
        plan: Step[TIn] | None,
        fn: Callable[[TIn], TOut],
    ) -> None:
        super().__init__()
        self._fn = fn
        self._dep_id: int | None = None
        if plan is not None:
            self._dep_id = self.add_dependency(plan)

        # Check for sync/safe marker
        if getattr(fn, "is_sync_and_safe", False):
            self.is_sync_and_safe = True

    def to_string_meta(self) -> str | None:
        return getattr(self._fn, "__name__", None) or getattr(
            self._fn, "display_name", None
        )

    def unbatched_execute(self, *args: Any) -> TOut:
        if self._dep_id is not None:
            return self._fn(args[0])
        return self._fn(None)  # type: ignore

    def execute(self, details: ExecutionDetails) -> list[TOut]:
        fn = self._fn
        results: list[TOut] = []
        for i in range(details.count):
            if self._dep_id is not None:
                value = details.values[0].at(i)
            else:
                value = None
            results.append(fn(value))
        return results


def _multistep(spec: Any) -> Step[Any] | None:
    """Convert a multistep spec into a single Step.

    - None → None
    - Step → Step
    - list/tuple of Steps → ListStep
    - dict of Steps → ObjectStep (not yet implemented)
    """
    if spec is None:
        return None
    if isinstance(spec, Step):
        return spec
    if isinstance(spec, (list, tuple)):
        from .list_step import ListStep

        return ListStep(spec)
    raise TypeError(f"Unsupported multistep spec: {type(spec)}")


def lambda_(
    spec: Any,
    fn: Callable[..., Any],
    is_sync_and_safe: bool = False,
) -> LambdaStep[Any, Any]:
    """Create a LambdaStep.

    spec can be:
    - A single Step
    - A list/tuple of Steps (will be combined via ListStep)
    - None
    """
    plan = _multistep(spec)
    step = LambdaStep(plan, fn)
    if is_sync_and_safe:
        step.is_sync_and_safe = True
    return step
