"""SideEffectStep - like LambdaStep but marks the step as having side effects."""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from ..step import ExecutionDetails, Step, UnbatchedStep

TIn = TypeVar("TIn")
TOut = TypeVar("TOut")


class SideEffectStep(UnbatchedStep[TOut]):
    """Calls a function for each entry, marking the step as having side effects.

    Side effect steps:
    - Execute in order (not parallelized with other side effect steps)
    - If one errors, subsequent side effect steps are inhibited
    - Are never considered safe to optimize away
    """

    is_sync_and_safe = False

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

        # Mark as having side effects AFTER super().__init__() so that
        # this step captures the previous latest_side_effect_step first,
        # then becomes the new latest_side_effect_step for subsequent steps.
        self.has_side_effects = True

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


def side_effect(
    spec: Any,
    fn: Callable[..., Any],
) -> SideEffectStep[Any, Any]:
    """Create a SideEffectStep.

    Similar to lambda_() but marks the step as having side effects.
    Side effect steps execute sequentially and if one errors,
    subsequent side effect steps are inhibited.

    spec can be:
    - A single Step
    - A list/tuple of Steps (will be combined via ListStep)
    - None
    """
    from .lambda_step import _multistep

    plan = _multistep(spec)
    return SideEffectStep(plan, fn)
