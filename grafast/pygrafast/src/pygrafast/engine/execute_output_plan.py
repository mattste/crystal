"""Execute output plans to serialize bucket results into GraphQL response."""

from __future__ import annotations

from typing import Any

from ..error import FlaggedValue, is_flagged_value
from .execute_bucket import Bucket
from .output_plan import OutputPlan


def execute_output_plan(
    output_plan: OutputPlan,
    bucket: Bucket,
    index: int = 0,
) -> Any:
    """Serialize a single entry from a bucket according to the output plan."""
    mode = output_plan.mode

    if mode == "root" or mode == "object":
        return _execute_object_output(output_plan, bucket, index)
    elif mode == "leaf":
        return _execute_leaf_output(output_plan, bucket, index)
    elif mode == "polymorphic":
        return _execute_polymorphic_output(output_plan, bucket, index)
    elif mode == "null":
        return None
    else:
        raise ValueError(f"Unsupported output mode: {mode}")


def _execute_object_output(
    output_plan: OutputPlan,
    bucket: Bucket,
    index: int,
) -> dict[str, Any] | None:
    """Build an object result from the output plan's children."""
    # If the object's own root step returned null, the whole object is null
    if output_plan.root_step is not None:
        obj_value = _get_step_value(output_plan.root_step, bucket, index)
        if obj_value is None or is_flagged_value(obj_value):
            return None

    result: dict[str, Any] = {}

    for key in output_plan.keys:
        child_output, child_step = output_plan.children[key]
        result[key] = execute_output_plan(child_output, bucket, index)

    return result


def _execute_polymorphic_output(
    output_plan: OutputPlan,
    bucket: Bucket,
    index: int,
) -> dict[str, Any] | None:
    """Build a polymorphic object result, selecting fields based on __typename."""
    # Check if the root step value is null
    if output_plan.root_step is not None:
        obj_value = _get_step_value(output_plan.root_step, bucket, index)
        if obj_value is None or is_flagged_value(obj_value):
            return None

    # Resolve __typename
    typename: str | None = None
    if output_plan.typename_step is not None:
        typename = _get_step_value(output_plan.typename_step, bucket, index)

    if typename is None:
        return None

    result: dict[str, Any] = {}

    # First, add common fields (fields defined on the interface itself)
    for key in output_plan.keys:
        child_output, child_step = output_plan.children[key]
        if key == "__typename":
            result["__typename"] = typename
        else:
            result[key] = execute_output_plan(child_output, bucket, index)

    # Then, add type-specific fields (from inline fragments)
    if typename in output_plan.type_keys:
        type_keys = output_plan.type_keys[typename]
        type_children = output_plan.type_children.get(typename, {})
        for key in type_keys:
            if key in type_children:
                child_output, child_step = type_children[key]
                result[key] = execute_output_plan(child_output, bucket, index)

    return result


def _execute_leaf_output(
    output_plan: OutputPlan,
    bucket: Bucket,
    index: int,
) -> Any:
    """Get a leaf value, applying serialization if needed."""
    step = output_plan.root_step
    if step is None:
        return None

    value = _get_step_value(step, bucket, index)

    if is_flagged_value(value):
        return None

    if value is None:
        return None

    # Apply serializer if present
    if output_plan.serializer is not None:
        try:
            return output_plan.serializer(value)
        except Exception:
            return value

    return value


def _get_step_value(step: Any, bucket: Bucket, index: int) -> Any:
    """Get the value for a step at a given index in the bucket."""
    step_id = step.id
    if step_id not in bucket.store:
        return None

    stored = bucket.store[step_id]

    # If step is unary or stored value is not a list, return directly
    if step._is_unary:
        return stored

    # Otherwise index into the list
    if isinstance(stored, list):
        if index < len(stored):
            return stored[index]
        return None

    return stored
