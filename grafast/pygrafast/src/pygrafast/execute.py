"""Main entry point for pygrafast execution."""

from __future__ import annotations

from dataclasses import dataclass, field
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
from .middleware import Middleware


@dataclass
class GrafastResult:
    """The result of a grafast execution."""

    data: dict[str, Any] | None = None
    errors: list[Any] | None = None
    extensions: dict[str, Any] | None = None


async def grafast(
    *,
    schema: GraphQLSchema,
    source: str,
    variable_values: dict[str, Any] | None = None,
    context_value: Any = None,
    operation_name: str | None = None,
    middleware: Middleware | dict[str, Any] | None = None,
) -> GrafastResult:
    """Execute a GraphQL operation using grafast's planning engine.

    This is the main entry point, equivalent to the TypeScript grafast() function.

    Parameters:
        schema: The GraphQL schema to execute against.
        source: The GraphQL query string.
        variable_values: Optional variables for the operation.
        context_value: Optional context value passed to resolvers/steps.
        operation_name: Optional name to select when the document has
            multiple operations.
        middleware: Optional middleware to intercept execution phases.
            Can be a :class:`Middleware` instance or a dict mapping phase
            names to callbacks (will be wrapped in ``Middleware.from_dict``).
    """
    # Normalise middleware
    if middleware is None:
        mw = Middleware()
    elif isinstance(middleware, dict):
        mw = Middleware.from_dict(middleware)
    else:
        mw = middleware

    # Build a mutable args dict so middleware can modify it
    exec_args: dict[str, Any] = {
        "schema": schema,
        "source": source,
        "variable_values": variable_values,
        "context_value": context_value,
        "operation_name": operation_name,
    }

    async def _run_pipeline() -> GrafastResult:
        """The core pipeline, wrapped by the 'execute' middleware phase."""
        _schema = exec_args["schema"]
        _source = exec_args["source"]
        _variable_values = exec_args["variable_values"]
        _context_value = exec_args["context_value"]
        _operation_name = exec_args["operation_name"]

        # --- parseAndValidate phase ---
        parse_args: dict[str, Any] = {
            "schema": _schema,
            "source": _source,
        }

        def _default_parse_and_validate() -> tuple[DocumentNode, list[Any]]:
            doc = parse(parse_args["source"])
            errs = validate(parse_args["schema"], doc)
            return doc, errs

        document: DocumentNode
        validation_errors: list[Any]
        pv_result = mw.run("parseAndValidate", parse_args, _default_parse_and_validate)
        if isinstance(pv_result, tuple):
            document, validation_errors = pv_result
        else:
            # Middleware returned something unexpected; treat as error
            return GrafastResult(errors=[Exception("parseAndValidate middleware returned invalid result")])

        if validation_errors:
            return GrafastResult(errors=validation_errors)

        # Find the operation
        operation = _find_operation(document, _operation_name)
        if operation is None:
            return GrafastResult(
                errors=[Exception(f"Operation '{_operation_name}' not found")]
            )

        # --- establishOperationPlan phase ---
        plan_args: dict[str, Any] = {
            "schema": _schema,
            "document": document,
            "operation": operation,
            "variable_values": _variable_values,
        }

        def _default_plan() -> OperationPlan:
            return OperationPlan(
                schema=plan_args["schema"],
                document=plan_args["document"],
                operation=plan_args["operation"],
                variable_values=plan_args["variable_values"],
            )

        try:
            op_plan = mw.run("establishOperationPlan", plan_args, _default_plan)
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
                    bucket.set_unary(step.id, _context_value if _context_value is not None else {})
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

    # Wrap the entire pipeline in the "execute" middleware phase
    result = await mw.run_async("execute", exec_args, _run_pipeline)
    return result


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
