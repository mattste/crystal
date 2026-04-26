"""Bucket execution - runs steps within a LayerPlan."""

from __future__ import annotations

from typing import Any

from ..constants import FLAG_ERROR, NO_FLAGS, ExecutionEntryFlags
from ..error import FlaggedValue, is_flagged_value
from ..step import ExecutionDetails, ExecutionValue, Step
from .layer_plan import LayerPlan


class Bucket:
    """Runtime container holding results for a LayerPlan."""

    __slots__ = ("layer_plan", "size", "store", "flags", "_non_unary_overrides")

    def __init__(
        self,
        layer_plan: LayerPlan,
        size: int,
    ) -> None:
        self.layer_plan = layer_plan
        self.size = size
        # step_id -> list of values (one per entry in bucket)
        self.store: dict[int, list[Any] | Any] = {}
        # step_id -> list of flags (one per entry)
        self.flags: dict[int, list[ExecutionEntryFlags]] = {}
        # Steps that should be treated as non-unary in this bucket,
        # even if the step object is marked _is_unary = True.
        # Used by sub-buckets created for array element execution.
        self._non_unary_overrides: set[int] = set()

    def set_unary(self, step_id: int, value: Any) -> None:
        """Set a unary (single) value for a step."""
        self.store[step_id] = value

    def get_unary(self, step_id: int) -> Any:
        """Get a unary value for a step."""
        return self.store[step_id]


def new_bucket(layer_plan: LayerPlan, size: int) -> Bucket:
    """Create a new bucket for the given layer plan."""
    return Bucket(layer_plan, size)


def execute_bucket(bucket: Bucket) -> None:
    """Execute all steps within a bucket's layer plan.

    Processes each phase in order, executing each step and storing results.
    """
    layer_plan = bucket.layer_plan

    for phase in layer_plan.phases:
        for step in phase:
            _execute_step(step, bucket)


def _execute_step(step: Step[Any], bucket: Bucket) -> None:
    """Execute a single step within a bucket."""
    # Build execution values for each dependency
    dep_values: list[ExecutionValue] = []
    for dep in step.dependencies:
        dep_id = dep.id
        if dep_id in bucket.store:
            stored = bucket.store[dep_id]
            if dep._is_unary:
                dep_values.append(
                    ExecutionValue(is_unary=True, unary_value=stored)
                )
            else:
                dep_values.append(ExecutionValue(entries=stored))
        else:
            # Dependency not in store — unary None
            dep_values.append(ExecutionValue(is_unary=True, unary_value=None))

    details = ExecutionDetails(count=bucket.size, values=dep_values)
    details._bucket = bucket  # type: ignore[attr-defined]

    # Execute the step
    try:
        results = step.execute(details)
    except Exception as e:
        # On error, fill results with flagged errors
        flagged = FlaggedValue(FLAG_ERROR, e)
        results = [flagged] * bucket.size

    # Store results
    if step._is_unary:
        # Unary step — store single value (not the list)
        bucket.store[step.id] = results[0] if results else None
    else:
        bucket.store[step.id] = results

    # Track flags
    flags: list[ExecutionEntryFlags] = []
    for r in (results if isinstance(results, list) else [results]):
        if is_flagged_value(r):
            flags.append(r.flag)
        else:
            flags.append(NO_FLAGS)
    bucket.flags[step.id] = flags
