"""Build a GraphQL schema with grafast plan resolvers."""

from __future__ import annotations

from typing import Any, Callable

from graphql import (
    GraphQLSchema,
    build_ast_schema,
    parse,
)

from .engine.operation_plan import GRAFAST_PLAN_RESOLVER_KEY, GRAFAST_PLAN_TYPE_KEY


def make_grafast_schema(
    *,
    type_defs: str,
    objects: dict[str, Any] | None = None,
    interfaces: dict[str, Any] | None = None,
    unions: dict[str, Any] | None = None,
    scalars: dict[str, Any] | None = None,
    enums: dict[str, Any] | None = None,
    input_objects: dict[str, Any] | None = None,
    enable_defer_stream: bool = False,
) -> GraphQLSchema:
    """Build a GraphQL schema from type definitions and plan resolvers.

    This is the Python equivalent of grafast's makeGrafastSchema.
    """
    document = parse(type_defs)
    schema = build_ast_schema(document)

    # Apply plan resolvers to object types
    if objects:
        _apply_object_plans(schema, objects)

    # Apply interface planType configs
    if interfaces:
        _apply_abstract_type_plans(schema, interfaces)

    # Apply union planType configs
    if unions:
        _apply_abstract_type_plans(schema, unions)

    # Apply enum value configs
    if enums:
        _apply_enum_plans(schema, enums)

    return schema


def _apply_object_plans(
    schema: GraphQLSchema,
    objects: dict[str, Any],
) -> None:
    """Apply plan resolvers from the objects config to schema fields."""
    type_map = schema.type_map

    for type_name, type_config in objects.items():
        gql_type = type_map.get(type_name)
        if gql_type is None:
            continue
        if not hasattr(gql_type, "fields"):
            continue

        plans = type_config.get("plans") if isinstance(type_config, dict) else None
        if plans is None:
            continue

        fields = gql_type.fields  # type: ignore
        for field_name, plan_resolver in plans.items():
            if field_name not in fields:
                continue

            field = fields[field_name]

            # plan_resolver can be a function directly or a config dict
            if callable(plan_resolver):
                resolver_fn = plan_resolver
            elif isinstance(plan_resolver, dict) and "plan" in plan_resolver:
                resolver_fn = plan_resolver["plan"]
            else:
                continue

            # Store the plan resolver in field extensions
            if not field.extensions:
                field.extensions = {}
            # graphql-core extensions are frozen mappingproxy, we need to work around this
            ext = dict(field.extensions) if field.extensions else {}
            ext[GRAFAST_PLAN_RESOLVER_KEY] = resolver_fn
            object.__setattr__(field, "extensions", ext)


def _apply_abstract_type_plans(
    schema: GraphQLSchema,
    type_configs: dict[str, Any],
) -> None:
    """Apply planType from interface/union configs to schema types."""
    type_map = schema.type_map

    for type_name, type_config in type_configs.items():
        gql_type = type_map.get(type_name)
        if gql_type is None:
            continue

        plan_type_fn = None
        if isinstance(type_config, dict):
            plan_type_fn = type_config.get("planType")

        if plan_type_fn is not None:
            ext = dict(gql_type.extensions) if gql_type.extensions else {}
            ext[GRAFAST_PLAN_TYPE_KEY] = plan_type_fn
            object.__setattr__(gql_type, "extensions", ext)


def _apply_enum_plans(
    schema: GraphQLSchema,
    enums_config: dict[str, Any],
) -> None:
    """Apply enum value configs."""
    type_map = schema.type_map

    for type_name, enum_config in enums_config.items():
        gql_type = type_map.get(type_name)
        if gql_type is None:
            continue

        values_config = enum_config.get("values") if isinstance(enum_config, dict) else None
        if values_config is None:
            continue

        # Update enum values
        if hasattr(gql_type, "values"):
            for value_name, value_config in values_config.items():
                if value_name in gql_type.values:  # type: ignore
                    enum_value = gql_type.values[value_name]  # type: ignore
                    if isinstance(value_config, dict) and "value" in value_config:
                        object.__setattr__(enum_value, "value", value_config["value"])
