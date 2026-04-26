"""Main entry point for pygrafast execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from graphql import (
    DocumentNode,
    GraphQLSchema,
    OperationDefinitionNode,
    parse,
    validate,
)
from graphql.language import OperationType

from .engine.execute_bucket import Bucket, execute_bucket, new_bucket
from .engine.execute_output_plan import execute_output_plan
from .engine.operation_plan import OperationPlan


@dataclass
class GrafastResult:
    """The result of a grafast execution."""

    data: dict[str, Any] | None = None
    errors: list[Any] | None = None


async def grafast(
    *,
    schema: GraphQLSchema,
    source: str,
    variable_values: dict[str, Any] | None = None,
    context_value: Any = None,
    operation_name: str | None = None,
) -> GrafastResult:
    """Execute a GraphQL operation using grafast's planning engine.

    This is the main entry point, equivalent to the TypeScript grafast() function.
    """
    # Parse
    try:
        document = parse(source)
    except Exception as e:
        return GrafastResult(errors=[e])

    # Validate
    validation_errors = validate(schema, document)
    if validation_errors:
        return GrafastResult(errors=validation_errors)

    # Find the operation
    operation = _find_operation(document, operation_name)
    if operation is None:
        return GrafastResult(
            errors=[Exception(f"Operation '{operation_name}' not found")]
        )

    # Build the operation plan
    try:
        op_plan = OperationPlan(
            schema=schema,
            document=document,
            operation=operation,
            variable_values=variable_values,
        )
    except Exception as e:
        return GrafastResult(errors=[e])

    # Create and execute the root bucket
    bucket = new_bucket(op_plan.root_layer_plan, size=1)

    # Inject unary values for _no_exec steps (ValueStep, ContextStep, etc.)
    from .steps.context_step import ContextStep

    for step in op_plan.step_tracker.all_steps():
        if step._no_exec and step._is_unary:
            if isinstance(step, ContextStep):
                # Inject the context value
                bucket.set_unary(step.id, context_value or {})
            else:
                # ValueStep — inject empty root value
                bucket.set_unary(step.id, {})

    # Inject variable values for InputStaticLeafStep and TrackedValueStep
    # (these are already baked into the step at planning time)

    # Execute
    execute_bucket(bucket)

    # Serialize output
    if op_plan._output_plan is None:
        return GrafastResult(data=None)

    errors: list[Any] = []
    try:
        data = execute_output_plan(op_plan._output_plan, bucket, index=0, errors=errors)
    except Exception as e:
        return GrafastResult(errors=[e])

    return GrafastResult(data=data, errors=errors if errors else None)


def _find_operation(
    document: DocumentNode,
    operation_name: str | None,
) -> OperationDefinitionNode | None:
    """Find the operation definition in the document."""
    operations: list[OperationDefinitionNode] = []
    for defn in document.definitions:
        if isinstance(defn, OperationDefinitionNode):
            operations.append(defn)

    if not operations:
        return None

    if operation_name is not None:
        for op in operations:
            if op.name and op.name.value == operation_name:
                return op
        return None

    if len(operations) == 1:
        return operations[0]

    # Multiple operations without a name — ambiguous
    return None
