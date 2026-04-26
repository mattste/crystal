"""Conformance test: basics.

Port of grafast/__tests__/conformance/basics-test.ts.

Tests that pygrafast produces identical output to graphql-core for basic
scalar, object, interface, and union queries.
"""

import pytest

from .utils import assert_conformance, make_conformance_schema

schema = make_conformance_schema(
    """
    type Query implements Interface {
        boolean: Boolean
        int: Int
        float: Float
        string: String
        id: ID
        customScalar: CustomScalar
        enum: Enum
        object: Query
        interface: Interface
        union: Union
    }
    scalar CustomScalar
    enum Enum {
        VALUE
    }
    interface Interface {
        boolean: Boolean
        int: Int
        float: Float
        string: String
        id: ID
        customScalar: CustomScalar
        enum: Enum
        object: Query
        interface: Interface
        union: Union
    }
    union Union = Query
    """
)

source = """
    query {
        ...Leaves
        object {
            ...Leaves
        }
        interface {
            ...Leaves
        }
        union {
            ...Leaves
        }
    }
    fragment Leaves on Interface {
        boolean
        int
        float
        string
        id
        customScalar
        enum
    }
"""


@pytest.mark.asyncio
async def test_basics():
    await assert_conformance(schema, source, {"include": True})
