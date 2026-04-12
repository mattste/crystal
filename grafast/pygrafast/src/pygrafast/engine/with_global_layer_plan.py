"""Global context tracking for the current LayerPlan during planning."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from .layer_plan import LayerPlan

T = TypeVar("T")

_current_layer_plan: ContextVar[LayerPlan | None] = ContextVar(
    "_current_layer_plan", default=None
)
_current_polymorphic_paths: ContextVar[frozenset[str] | None] = ContextVar(
    "_current_polymorphic_paths", default=None
)


def current_layer_plan() -> LayerPlan:
    """Get the current layer plan (set during planning)."""
    lp = _current_layer_plan.get()
    if lp is None:
        raise RuntimeError(
            "No current layer plan - are you creating steps outside of planning?"
        )
    return lp


def current_polymorphic_paths() -> frozenset[str] | None:
    """Get the current polymorphic paths."""
    return _current_polymorphic_paths.get()


def with_global_layer_plan(
    layer_plan: LayerPlan,
    polymorphic_paths: frozenset[str] | None,
    callback: Any,
) -> Any:
    """Run callback with the given layer plan as the current global."""
    token_lp = _current_layer_plan.set(layer_plan)
    token_pp = _current_polymorphic_paths.set(polymorphic_paths)
    try:
        return callback()
    finally:
        _current_layer_plan.reset(token_lp)
        _current_polymorphic_paths.reset(token_pp)
