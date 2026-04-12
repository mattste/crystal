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
    elif mode == "array":
        return _execute_array_output(output_plan, bucket, index)
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


def _execute_array_output(
    output_plan: OutputPlan,
    bucket: Bucket,
    index: int,
) -> list[Any] | None:
    """Build an array result from the output plan."""
    step = output_plan.root_step
    if step is None:
        return None

    list_value = _get_step_value(step, bucket, index)

    if list_value is None or is_flagged_value(list_value):
        return None

    if not isinstance(list_value, (list, tuple)):
        return None

    elem_output = output_plan.element_output
    if elem_output is None:
        # No element output plan — just return the raw values
        return list(list_value)

    # For each element, build its output
    result: list[Any] = []
    for item in list_value:
        if item is None or is_flagged_value(item):
            result.append(None)
        elif elem_output.mode == "leaf":
            if elem_output.serializer is not None:
                try:
                    result.append(elem_output.serializer(item))
                except Exception:
                    result.append(item)
            else:
                result.append(item)
        elif elem_output.mode == "object":
            # For object elements, we need the item's properties
            # The step results are already the full objects from EachStep
            if isinstance(item, dict):
                obj: dict[str, Any] = {}
                for key in elem_output.keys:
                    child_out, child_step = elem_output.children[key]
                    if child_out.mode == "leaf":
                        val = item.get(key)
                        if child_out.serializer is not None and val is not None:
                            try:
                                val = child_out.serializer(val)
                            except Exception:
                                pass
                        obj[key] = val
                    elif child_out.mode == "object":
                        obj[key] = _extract_object_from_item(child_out, item.get(key))
                    elif child_out.mode == "array":
                        obj[key] = _extract_array_from_item(child_out, item.get(key))
                    else:
                        obj[key] = item.get(key)
                result.append(obj)
            else:
                result.append(None)
        else:
            result.append(item)

    return result


def _extract_object_from_item(
    output_plan: OutputPlan,
    item: Any,
) -> dict[str, Any] | None:
    """Extract object fields from an item dict using the output plan."""
    if item is None:
        return None
    if not isinstance(item, dict):
        return None

    result: dict[str, Any] = {}
    for key in output_plan.keys:
        child_out, _ = output_plan.children[key]
        val = item.get(key)
        if child_out.mode == "leaf":
            if child_out.serializer is not None and val is not None:
                try:
                    val = child_out.serializer(val)
                except Exception:
                    pass
            result[key] = val
        elif child_out.mode == "object":
            result[key] = _extract_object_from_item(child_out, val)
        elif child_out.mode == "array":
            result[key] = _extract_array_from_item(child_out, val)
        else:
            result[key] = val
    return result


def _extract_array_from_item(
    output_plan: OutputPlan,
    items: Any,
) -> list[Any] | None:
    """Extract array from items."""
    if items is None:
        return None
    if not isinstance(items, (list, tuple)):
        return None
    return list(items)


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
