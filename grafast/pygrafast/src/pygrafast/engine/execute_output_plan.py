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

    # If planForType explicitly returned None for this type, render as null
    if typename in output_plan.null_types:
        return None

    result: dict[str, Any] = {}

    # First, add common fields (fields defined on the interface itself)
    for key in output_plan.keys:
        child_output, child_step = output_plan.children[key]
        if key == "__typename":
            result["__typename"] = typename
        else:
            result[key] = execute_output_plan(child_output, bucket, index)

    # Determine which type_keys entries apply to this typename.
    # This includes the concrete type itself AND any interfaces/abstract
    # types it implements, since `... on SomeInterface { field }` applies
    # to all concrete types implementing that interface.
    applicable_type_names = _get_applicable_type_names(
        typename, output_plan
    )

    # Then, add type-specific fields (from inline fragments)
    for type_name in applicable_type_names:
        if type_name in output_plan.type_keys:
            type_keys = output_plan.type_keys[type_name]
            type_children = output_plan.type_children.get(type_name, {})
            for key in type_keys:
                if key not in result and key in type_children:
                    child_output, child_step = type_children[key]
                    result[key] = execute_output_plan(child_output, bucket, index)

    return result


def _get_applicable_type_names(
    typename: str, output_plan: OutputPlan
) -> list[str]:
    """Get all type names whose inline fragment fields should apply for the
    given concrete typename.  This includes the concrete type itself plus
    any interfaces it implements that have type-specific fields."""
    names = [typename]

    # Access the schema through the output plan's layer plan
    try:
        schema = output_plan.layer_plan.operation_plan.schema
    except AttributeError:
        return names

    concrete_type = schema.type_map.get(typename)
    if concrete_type is None:
        return names

    from graphql import GraphQLObjectType
    if isinstance(concrete_type, GraphQLObjectType):
        for iface in concrete_type.interfaces:
            if iface.name in output_plan.type_keys and iface.name not in names:
                names.append(iface.name)

    return names


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

    # For object/polymorphic elements that have steps needing execution,
    # use a sub-bucket to properly execute all dependent steps.
    if elem_output.mode in ("object", "polymorphic") and len(list_value) > 0:
        return _execute_array_elements_via_bucket(
            output_plan, elem_output, step, list_value, bucket
        )

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
        elif elem_output.mode in ("object", "polymorphic"):
            # For object/polymorphic elements, extract selected fields from the dict
            if isinstance(item, dict):
                result.append(_extract_object_from_item(elem_output, item))
            else:
                result.append(None)
        else:
            result.append(item)

    return result


def _collect_element_steps(elem_output: OutputPlan, array_step: Any) -> list[Any]:
    """Collect all steps referenced by an element output plan that depend
    (directly or transitively) on the array step.  Returns them in
    topological (registration-id) order."""
    from ..step import Step

    # Gather every step referenced by the element output plan
    referenced: set[int] = set()

    def _gather_from_output(op: OutputPlan) -> None:
        if op.root_step is not None:
            referenced.add(op.root_step.id)
        if op.typename_step is not None:
            referenced.add(op.typename_step.id)
        for _key, (child_out, child_step) in op.children.items():
            if child_step is not None:
                referenced.add(child_step.id)
            _gather_from_output(child_out)
        for _tn, tc in op.type_children.items():
            for _key, (child_out, child_step) in tc.items():
                if child_step is not None:
                    referenced.add(child_step.id)
                _gather_from_output(child_out)
        if op.element_output is not None:
            _gather_from_output(op.element_output)

    _gather_from_output(elem_output)

    # Now walk backwards from every referenced step to collect all transitive
    # dependencies (stopping at the array_step which is the "root" for elements).
    needed: set[int] = set()
    array_step_id = array_step.id

    def _walk(step: Step) -> None:  # type: ignore[type-arg]
        if step.id in needed:
            return
        if step.id == array_step_id:
            # Don't add the array step itself – it's the input, not something
            # to execute.
            return
        needed.add(step.id)
        for dep in step.dependencies:
            _walk(dep)

    all_steps = array_step.operation_plan.step_tracker.all_steps()
    for sid in list(referenced):
        for s in all_steps:
            if s.id == sid:
                _walk(s)
                break

    # Return in registration order (topological order).
    return [s for s in all_steps if s.id in needed]


def _execute_array_elements_via_bucket(
    array_output: OutputPlan,
    elem_output: OutputPlan,
    array_step: Any,
    items: list | tuple,
    parent_bucket: Bucket,
) -> list[Any]:
    """Execute element-level steps in a sub-bucket so that polymorphic
    resolution, nested plan resolvers, and type-specific fields all work."""
    from ..step import ExecutionDetails, ExecutionValue
    from .execute_bucket import _execute_step

    n = len(items)
    sub_bucket = Bucket(parent_bucket.layer_plan, n)

    # Store the individual items under the array_step's ID.
    # This makes them available as a batch to steps that depend on the
    # array_step (e.g. AccessStep for field extraction, LambdaStep for
    # __typename resolution).
    sub_bucket.store[array_step.id] = list(items)
    # Mark the array_step as non-unary in this sub-bucket so that
    # _get_step_value indexes into the list per element.
    sub_bucket._non_unary_overrides.add(array_step.id)

    # Copy unary values from the parent bucket (context, constants, etc.)
    for step_id, value in parent_bucket.store.items():
        if step_id == array_step.id:
            continue
        step_obj = array_step.operation_plan.step_tracker.get_step_by_id(step_id)
        if step_obj is not None and step_obj._is_unary:
            sub_bucket.store[step_id] = value

    # Collect and execute all steps needed by the element output plan.
    steps_to_exec = _collect_element_steps(elem_output, array_step)

    for s in steps_to_exec:
        if s._no_exec:
            continue
        # Build execution values for each dependency.
        dep_values: list[ExecutionValue] = []
        for dep in s.dependencies:
            dep_id = dep.id
            if dep_id in sub_bucket.store:
                stored = sub_bucket.store[dep_id]
                # In the sub-bucket the array_step's value is a list of items
                # (non-unary), but other steps that were unary in the parent
                # bucket remain unary.  Check the override set first.
                if dep_id in sub_bucket._non_unary_overrides:
                    dep_values.append(ExecutionValue(entries=stored))
                elif dep._is_unary:
                    dep_values.append(
                        ExecutionValue(is_unary=True, unary_value=stored)
                    )
                else:
                    if isinstance(stored, list):
                        dep_values.append(ExecutionValue(entries=stored))
                    else:
                        dep_values.append(
                            ExecutionValue(is_unary=True, unary_value=stored)
                        )
            else:
                dep_values.append(
                    ExecutionValue(is_unary=True, unary_value=None)
                )

        details = ExecutionDetails(count=n, values=dep_values)
        details._bucket = sub_bucket  # type: ignore[attr-defined]

        try:
            results = s.execute(details)
        except Exception as e:
            from ..error import FlaggedValue
            from ..constants import FLAG_ERROR
            flagged = FlaggedValue(FLAG_ERROR, e)
            results = [flagged] * n

        # Store results as a list and mark as non-unary in this bucket
        sub_bucket.store[s.id] = results
        sub_bucket._non_unary_overrides.add(s.id)

    # Now read out results using the element output plan.
    result: list[Any] = []
    for i in range(n):
        item = items[i]
        if item is None or is_flagged_value(item):
            result.append(None)
        else:
            result.append(execute_output_plan(elem_output, sub_bucket, i))
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

    # Extract common fields
    for key in output_plan.keys:
        if key in output_plan.children:
            child_out, _ = output_plan.children[key]
            val = item.get(key)
            if child_out.mode == "leaf":
                if child_out.serializer is not None and val is not None:
                    try:
                        val = child_out.serializer(val)
                    except Exception:
                        pass
                result[key] = val
            elif child_out.mode in ("object", "polymorphic"):
                result[key] = _extract_object_from_item(child_out, val)
            elif child_out.mode == "array":
                result[key] = _extract_array_from_item(child_out, val)
            else:
                result[key] = val

    # For polymorphic mode, also extract type-specific fields
    if output_plan.mode == "polymorphic":
        # Determine the __typename from the item
        typename = item.get("__typename") or item.get("type")
        if typename and typename in output_plan.type_keys:
            type_keys = output_plan.type_keys[typename]
            type_children = output_plan.type_children.get(typename, {})
            for key in type_keys:
                if key in type_children:
                    child_out, _ = type_children[key]
                    val = item.get(key)
                    if child_out.mode == "leaf":
                        if child_out.serializer is not None and val is not None:
                            try:
                                val = child_out.serializer(val)
                            except Exception:
                                pass
                        result[key] = val
                    elif child_out.mode in ("object", "polymorphic"):
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

    # If step is unary (and not overridden in this bucket), return directly
    if step._is_unary and step_id not in bucket._non_unary_overrides:
        return stored

    # Otherwise index into the list
    if isinstance(stored, list):
        if index < len(stored):
            return stored[index]
        return None

    return stored
