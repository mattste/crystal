"""Tracer 1 RED: Simplest possible end-to-end test.

Port of grafastSync.test.ts — a scalar query using lambda_ and make_grafast_schema.
"""

import pytest

from pygrafast import grafast, make_grafast_schema
from pygrafast.steps import lambda_


@pytest.mark.asyncio
async def test_add_two_numbers():
    schema = make_grafast_schema(
        type_defs="type Query { addTwoNumbers(a: Int!, b: Int!): Int }",
        objects={
            "Query": {
                "plans": {
                    "addTwoNumbers": lambda _parent, field_args: lambda_(
                        [field_args.get_raw("a"), field_args.get_raw("b")],
                        lambda args: args[0] + args[1],
                    ),
                },
            },
        },
    )
    result = await grafast(schema=schema, source="{ addTwoNumbers(a: 7, b: 13) }")
    assert result.errors is None
    assert result.data == {"addTwoNumbers": 20}


@pytest.mark.asyncio
async def test_add_two_numbers_with_variables():
    schema = make_grafast_schema(
        type_defs="type Query { addTwoNumbers(a: Int!, b: Int!): Int }",
        objects={
            "Query": {
                "plans": {
                    "addTwoNumbers": lambda _parent, field_args: lambda_(
                        [field_args.get_raw("a"), field_args.get_raw("b")],
                        lambda args: args[0] + args[1],
                    ),
                },
            },
        },
    )
    result = await grafast(
        schema=schema,
        source="query AddTwo($a: Int!, $b: Int!) { addTwoNumbers(a: $a, b: $b) }",
        variable_values={"a": 9, "b": 12},
    )
    assert result.errors is None
    assert result.data == {"addTwoNumbers": 21}
