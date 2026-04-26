"""Conformance test utilities.

Port of grafast/__tests__/conformance/utils.ts.

Builds a schema where every field returns a deterministic constant based on its
return type, then verifies that pygrafast produces identical output to standard
graphql-core execution.
"""

from __future__ import annotations

from typing import Any

from graphql import (
    GraphQLOutputType,
    GraphQLSchema,
    build_schema,
    graphql as graphql_execute,
    is_enum_type,
    is_interface_type,
    is_list_type,
    is_non_null_type,
    is_object_type,
    is_scalar_type,
    is_union_type,
)

from pygrafast import grafast, make_grafast_schema
from pygrafast.steps.constant import constant
from pygrafast.steps.get import get


def _value_for_type(schema: GraphQLSchema, type_: GraphQLOutputType) -> Any:
    """Return a deterministic constant value for a given GraphQL output type."""
    if is_non_null_type(type_):
        return _value_for_type(schema, type_.of_type)
    elif is_list_type(type_):
        value = _value_for_type(schema, type_.of_type)
        return [value, value]
    elif is_object_type(type_):
        return {}
    elif is_union_type(type_):
        type_names = sorted(t.name for t in type_.types)
        return {"__typename": type_names[0]}
    elif is_interface_type(type_):
        impls = schema.get_implementations(type_)
        type_names = sorted(t.name for t in impls.objects)
        return {"__typename": type_names[0]}
    elif is_scalar_type(type_):
        name = type_.name
        if name == "Boolean":
            return True
        elif name == "Int":
            return 2
        elif name == "Float":
            return 3.14
        elif name == "ID":
            return "id"
        else:
            return "str"
    elif is_enum_type(type_):
        values = list(type_.values.values())
        first = values[0]
        return first.value if first.value is not None else first.name
    else:
        raise TypeError(f"Type {type_} not understood")


def _plan_type(specifier):
    """planType for interfaces and unions -- reads __typename from specifier."""
    return {"$__typename": get(specifier, "__typename")}


def _make_field_plans(
    schema: GraphQLSchema,
    fields: dict,
) -> dict:
    """Build plan resolvers for all fields of an object type."""
    plans: dict[str, Any] = {}
    for field_name, field_def in fields.items():
        value = _value_for_type(schema, field_def.type)
        # Plan resolvers in pygrafast receive (parent_step, field_args)
        # We need to capture value in the closure properly
        def make_plan(v: Any = value):
            return lambda _parent, _field_args: constant(v)
        plans[field_name] = make_plan()
    return plans


def make_conformance_schema(schema_text: str) -> GraphQLSchema:
    """Build a conformance schema from SDL text.

    Every field gets a plan resolver returning a deterministic constant.
    Interface/union types get a planType that reads __typename from the
    specifier.

    The original graphql-core schema is stored in the returned schema's
    ``extensions`` under the key ``"graphqljsSchema"``.
    """
    graphqljs_schema = build_schema(schema_text)

    objects: dict[str, Any] = {}
    interfaces: dict[str, Any] = {}
    unions: dict[str, Any] = {}

    for type_ in graphqljs_schema.type_map.values():
        if is_object_type(type_):
            plans = _make_field_plans(graphqljs_schema, type_.fields)
            objects[type_.name] = {"plans": plans}
        elif is_interface_type(type_):
            plans = _make_field_plans(graphqljs_schema, type_.fields)
            interfaces[type_.name] = {"planType": _plan_type, "plans": plans}
        elif is_union_type(type_):
            unions[type_.name] = {"planType": _plan_type}

    schema = make_grafast_schema(
        type_defs=schema_text,
        objects=objects,
        interfaces=interfaces,
        unions=unions,
    )

    # Store the original graphql-core schema in extensions for assertConformance
    ext = dict(schema.extensions) if schema.extensions else {}
    ext["graphqljsSchema"] = graphqljs_schema
    object.__setattr__(schema, "extensions", ext)

    return schema


async def assert_conformance(
    schema: GraphQLSchema,
    source: str,
    variable_values: dict[str, Any] | None = None,
) -> None:
    """Assert that pygrafast produces identical output to graphql-core.

    Runs the query through both:
    - Standard graphql-core with a field_resolver returning deterministic values
    - pygrafast
    Then asserts the results are deeply equal.
    """
    graphqljs_schema = (schema.extensions or {}).get("graphqljsSchema")
    if graphqljs_schema is None:
        raise RuntimeError(
            "Conformance schema must be built with make_conformance_schema()"
        )

    def field_resolver(root_value: Any, info: Any, **kwargs: Any) -> Any:
        return _value_for_type(info.schema, info.return_type)

    def type_resolver(value: Any, info: Any, abstract_type: Any) -> str | None:
        if isinstance(value, dict):
            return value.get("__typename")
        return None

    graphqljs_result = await graphql_execute(
        schema,
        source,
        variable_values=variable_values,
        field_resolver=field_resolver,
        type_resolver=type_resolver,
    )

    # Verify graphql-core produced a valid result
    assert graphqljs_result.data is not None, (
        f"graphql-core returned no data: {graphqljs_result.errors}"
    )
    assert graphqljs_result.errors is None, (
        f"graphql-core returned errors: {graphqljs_result.errors}"
    )

    grafast_result = await grafast(
        schema=schema,
        source=source,
        variable_values=variable_values,
    )

    # Compare results
    assert grafast_result.errors is None, (
        f"grafast returned errors: {grafast_result.errors}"
    )
    assert grafast_result.data == graphqljs_result.data, (
        f"Results differ!\n"
        f"  graphql-core: {graphqljs_result.data}\n"
        f"  grafast:      {grafast_result.data}"
    )
