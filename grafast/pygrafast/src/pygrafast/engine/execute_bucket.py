"""Bucket execution - runs steps within a LayerPlan."""

from __future__ import annotations

from typing import Any

from ..constants import DEFAULT_FORBIDDEN_FLAGS, FLAG_ERROR, FLAG_NULL, NO_FLAGS, ExecutionEntryFlags
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


def _get_dep_flags(dep: Step[Any], bucket: Bucket, index: int) -> ExecutionEntryFlags:
    """Get the flags for a dependency at a given index."""
    dep_id = dep.id
    if dep_id in bucket.flags:
        dep_flags = bucket.flags[dep_id]
        if isinstance(dep_flags, list) and index < len(dep_flags):
            return dep_flags[index]
    # No explicit flags — check the stored value
    if dep_id in bucket.store:
        stored = bucket.store[dep_id]
        if dep._is_unary or not isinstance(stored, list):
            val = stored
        elif index < len(stored):
            val = stored[index]
        else:
            val = None
        if is_flagged_value(val):
            return val.flag
        if val is None:
            return FLAG_NULL
    return NO_FLAGS


def _execute_step(step: Step[Any], bucket: Bucket) -> None:
    """Execute a single step within a bucket."""
    # Check if a prior side-effect step errored. If so, propagate the
    # error to this step without executing it.  This implements the
    # cancellation of steps that follow a failed side effect.
    se_step = step.implicit_side_effect_step
    if se_step is not None and se_step.id in bucket.store:
        se_stored = bucket.store[se_step.id]
        if is_flagged_value(se_stored) and (se_stored.flag & FLAG_ERROR):
            # Propagate the error from the side effect step
            bucket.store[step.id] = se_stored
            bucket.flags[step.id] = [se_stored.flag] * max(bucket.size, 1)
            return
        # For non-unary side effect results, check per-entry
        if isinstance(se_stored, list):
            for val in se_stored:
                if is_flagged_value(val) and (val.flag & FLAG_ERROR):
                    bucket.store[step.id] = se_stored
                    bucket.flags[step.id] = [
                        v.flag if is_flagged_value(v) else NO_FLAGS
                        for v in se_stored
                    ]
                    return

    # Check if any dependency value is flagged and forbidden for this step.
    # If so, propagate the flagged value instead of executing the step.
    # This mirrors the TS behaviour where the bucket execution checks
    # forbidden flags per-entry.
    forbidden_flags_list = step._dependency_forbidden_flags

    # For unary steps, check once
    if step._is_unary:
        for dep_idx, dep in enumerate(step.dependencies):
            dep_id = dep.id
            forbidden = forbidden_flags_list[dep_idx] if dep_idx < len(forbidden_flags_list) else DEFAULT_FORBIDDEN_FLAGS
            dep_flags = _get_dep_flags(dep, bucket, 0)
            disallowed = dep_flags & forbidden
            if disallowed:
                # This dependency has a forbidden flag — propagate it
                if dep_id in bucket.store:
                    stored = bucket.store[dep_id]
                    if is_flagged_value(stored):
                        bucket.store[step.id] = stored
                        bucket.flags[step.id] = [stored.flag]
                        return
                # Null value that's forbidden — create a flagged null
                fv = FlaggedValue(FLAG_NULL, None)
                bucket.store[step.id] = fv
                bucket.flags[step.id] = [FLAG_NULL]
                return

    # For batch steps, build a per-entry skip mask.
    skip_mask: list[FlaggedValue | None] | None = None
    if not step._is_unary and bucket.size > 0:
        skip_mask = [None] * bucket.size
        for dep_idx, dep in enumerate(step.dependencies):
            dep_id = dep.id
            forbidden = forbidden_flags_list[dep_idx] if dep_idx < len(forbidden_flags_list) else DEFAULT_FORBIDDEN_FLAGS

            for j in range(bucket.size):
                if skip_mask[j] is not None:
                    continue
                dep_flags = _get_dep_flags(dep, bucket, j)
                disallowed = dep_flags & forbidden
                if disallowed:
                    # Get the actual value to propagate
                    if dep_id in bucket.store:
                        stored = bucket.store[dep_id]
                        if dep._is_unary or not isinstance(stored, list):
                            val = stored
                        elif j < len(stored):
                            val = stored[j]
                        else:
                            val = None
                        if is_flagged_value(val):
                            skip_mask[j] = val
                        else:
                            skip_mask[j] = FlaggedValue(dep_flags, val)
                    else:
                        skip_mask[j] = FlaggedValue(FLAG_NULL, None)

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

    # Apply skip mask: entries that were skipped due to forbidden flags
    # get the propagated flagged value instead of the computed result.
    if skip_mask is not None and isinstance(results, list):
        for j in range(min(len(results), len(skip_mask))):
            if skip_mask[j] is not None:
                results[j] = skip_mask[j]

    # Store results
    if step._is_unary:
        # Unary step — store single value (not the list)
        bucket.store[step.id] = results[0] if results else None
    else:
        bucket.store[step.id] = results

    # Track flags — set FLAG_NULL for None results (mirrors TS behavior)
    flags: list[ExecutionEntryFlags] = []
    for r in (results if isinstance(results, list) else [results]):
        if is_flagged_value(r):
            flags.append(r.flag)
        elif r is None:
            flags.append(FLAG_NULL)
        else:
            flags.append(NO_FLAGS)
    bucket.flags[step.id] = flags
