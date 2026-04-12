"""ContextStep - provides access to the GraphQL context value during execution."""

from __future__ import annotations

from typing import Any

from ..step import ExecutionDetails, Step


class ContextStep(Step[Any]):
    """A step that reads a value from the GraphQL context.

    Created during planning to represent context access.
    At execution time, the context value is injected into the bucket store.
    """

    _no_exec = True
    is_sync_and_safe = True

    def __init__(self) -> None:
        super().__init__()
        self._is_unary = True

    def to_string_meta(self) -> str | None:
        return "context"

    def get(self, key: str) -> ContextAccessStep:
        """Access a property of the context value."""
        return ContextAccessStep(self, key)


class ContextAccessStep(Step[Any]):
    """Reads a specific key from the context value."""

    is_sync_and_safe = True

    def __init__(self, context_step: ContextStep, key: str) -> None:
        super().__init__()
        self._key = key
        self._context_dep_id = self.add_dependency(context_step)
        self._is_unary = True

    def to_string_meta(self) -> str | None:
        return f"context.{self._key}"

    def execute(self, details: ExecutionDetails) -> list[Any]:
        ctx = details.values[0].at(0)
        if isinstance(ctx, dict):
            value = ctx.get(self._key)
        else:
            value = getattr(ctx, self._key, None)
        return [value] * details.count


# Global context step factory
_context_step: ContextStep | None = None


def context() -> ContextStep:
    """Get a step representing the GraphQL context value.

    Must be called during planning (within a plan resolver).
    """
    from ..engine.with_global_layer_plan import with_global_layer_plan, current_layer_plan

    lp = current_layer_plan()

    def make_context() -> ContextStep:
        return ContextStep()

    return with_global_layer_plan(lp, None, make_context)
