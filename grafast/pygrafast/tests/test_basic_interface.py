"""Port of grafast/__tests__/basic-interface-test.ts

Tests interface type resolution, polymorphic dispatch, inline fragments,
__typename resolution, and null handling in polymorphic contexts.
"""

import pytest

from pygrafast import grafast, make_grafast_schema
from pygrafast.steps import constant, lambda_


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOTIFICATION_DATA = [
    {"type": "ready", "isReady": True, "id": "1"},
    {"type": "ready", "isReady": False, "id": "2"},
    {"type": "logout", "username": "benjie", "id": "3"},
]


def notification_to_type_name(obj):
    """Resolve a notification dict to its concrete GraphQL type name."""
    if obj is None:
        return None
    if obj.get("type") == "ready":
        return "UserNotificationReady"
    if obj.get("type") == "logout":
        return "UserNotificationLogout"
    return None


def _make_schema():
    """Build the notification interface schema (mirrors makeSchema in the TS test)."""
    return make_grafast_schema(
        type_defs="""
            interface UserNotification {
                id: ID!
            }

            type UserNotificationReady implements UserNotification {
                id: ID!
                isReady: Boolean!
            }

            type UserNotificationLogout implements UserNotification {
                id: ID!
                username: String!
            }

            type Query {
                notifications: [UserNotification!]!
            }
        """,
        objects={
            "Query": {
                "plans": {
                    "notifications": lambda _parent, _args: constant(
                        NOTIFICATION_DATA,
                    ),
                },
            },
        },
        interfaces={
            "UserNotification": {
                "planType": lambda step: {
                    "$__typename": lambda_(step, notification_to_type_name),
                },
            },
        },
    )


def _make_schema_with_no_implementations():
    """Build an interface with no implementing types (mirrors the TS test)."""
    return make_grafast_schema(
        type_defs="""
            interface UserNotification {
                id: ID!
            }

            type Query {
                notifications: [UserNotification!]!
            }
        """,
        objects={
            "Query": {
                "plans": {
                    "notifications": lambda _parent, _args: constant([]),
                },
            },
        },
    )


# ---------------------------------------------------------------------------
# Test 1: Schema has the correct structure
# ---------------------------------------------------------------------------

def test_schema_structure():
    """Interface type exists and has planType configured."""
    from graphql import GraphQLInterfaceType
    from pygrafast.engine.operation_plan import GRAFAST_PLAN_TYPE_KEY

    schema = _make_schema()
    notification_type = schema.type_map.get("UserNotification")

    assert notification_type is not None
    assert isinstance(notification_type, GraphQLInterfaceType)
    assert notification_type.extensions is not None
    assert GRAFAST_PLAN_TYPE_KEY in notification_type.extensions


# ---------------------------------------------------------------------------
# Test 2: Basic interface field resolution (id only)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_interface_basic_field():
    """Querying only the shared `id` field on the interface works."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="""
            query {
                notifications {
                    id
                }
            }
        """,
    )
    assert result.errors is None
    assert result.data == {
        "notifications": [
            {"id": "1"},
            {"id": "2"},
            {"id": "3"},
        ],
    }


# ---------------------------------------------------------------------------
# Test 3: __typename + inline fragments on concrete types
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_interface_typename_and_inline_fragments():
    """__typename resolves correctly and inline fragments dispatch to the right type."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="""
            query {
                notifications {
                    __typename
                    id
                    ... on UserNotificationReady {
                        isReady
                    }
                    ... on UserNotificationLogout {
                        username
                    }
                }
            }
        """,
    )
    assert result.errors is None
    assert result.data == {
        "notifications": [
            {
                "__typename": "UserNotificationReady",
                "id": "1",
                "isReady": True,
            },
            {
                "__typename": "UserNotificationReady",
                "id": "2",
                "isReady": False,
            },
            {
                "__typename": "UserNotificationLogout",
                "id": "3",
                "username": "benjie",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Test 4: Empty list with no implementing types
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_interface_no_implementations():
    """An interface with no implementations returning an empty list works."""
    schema = _make_schema_with_no_implementations()
    result = await grafast(
        schema=schema,
        source="""
            query {
                notifications {
                    id
                }
            }
        """,
    )
    assert result.errors is None
    assert result.data == {"notifications": []}


# ---------------------------------------------------------------------------
# Test 5: Only __typename (no other fields)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_interface_typename_only():
    """Querying only __typename on an interface list works."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="""
            query {
                notifications {
                    __typename
                }
            }
        """,
    )
    assert result.errors is None
    assert result.data == {
        "notifications": [
            {"__typename": "UserNotificationReady"},
            {"__typename": "UserNotificationReady"},
            {"__typename": "UserNotificationLogout"},
        ],
    }


# ---------------------------------------------------------------------------
# Test 6: Inline fragment on only one concrete type
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_interface_single_inline_fragment():
    """Only requesting fields from one concrete type; the other type omits them."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="""
            query {
                notifications {
                    id
                    ... on UserNotificationReady {
                        isReady
                    }
                }
            }
        """,
    )
    assert result.errors is None
    notifications = result.data["notifications"]
    # Ready notifications include isReady
    assert notifications[0] == {"id": "1", "isReady": True}
    assert notifications[1] == {"id": "2", "isReady": False}
    # Logout notification does NOT include isReady
    assert notifications[2] == {"id": "3"}


# ---------------------------------------------------------------------------
# Test 7: Nullable interface field returning null
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nullable_interface_field_null():
    """A nullable interface field that returns null resolves to null."""

    def resolve_type_name(obj):
        if obj is None:
            return None
        return "ItemA"

    schema = make_grafast_schema(
        type_defs="""
            interface Item {
                id: ID!
            }

            type ItemA implements Item {
                id: ID!
                label: String
            }

            type Query {
                item: Item
            }
        """,
        objects={
            "Query": {
                "plans": {
                    "item": lambda _parent, _args: constant(None),
                },
            },
        },
        interfaces={
            "Item": {
                "planType": lambda step: {
                    "$__typename": lambda_(step, resolve_type_name),
                },
            },
        },
    )
    result = await grafast(
        schema=schema,
        source="{ item { __typename id } }",
    )
    assert result.errors is None
    assert result.data == {"item": None}


# ---------------------------------------------------------------------------
# Test 8: Aliased fields on interface
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_interface_aliased_fields():
    """Field aliases work correctly on interface types."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="""
            query {
                notifications {
                    nid: id
                    kind: __typename
                }
            }
        """,
    )
    assert result.errors is None
    assert result.data == {
        "notifications": [
            {"nid": "1", "kind": "UserNotificationReady"},
            {"nid": "2", "kind": "UserNotificationReady"},
            {"nid": "3", "kind": "UserNotificationLogout"},
        ],
    }
