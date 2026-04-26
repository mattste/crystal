"""Error handling tests - port of errorHandling-test.ts.

Tests error propagation, null bubbling, and error handling in lists
through the pygrafast execution engine.
"""

import pytest

from pygrafast import grafast, make_grafast_schema
from pygrafast.steps import constant, lambda_


def _make_schema():
    """Build the test schema with error-producing resolvers."""
    from graphql import GraphQLError

    return make_grafast_schema(
        type_defs="""
            type OtherThing {
                id: Int
            }
            type Thing {
                id: Int
                throw: Int
            }
            type Query {
                list: [Thing!]
                listContainingErrors: [Int]
                nullableField: Int
                nonNullField: Int!
                errorField: Int
                nestedError: Thing
                multipleErrors: [Int]
            }
        """,
        objects={
            "Query": {
                "plans": {
                    "list": lambda _parent, _fa: constant([1, 2]),
                    "listContainingErrors": lambda _parent, _fa: lambda_(
                        None,
                        lambda _: [
                            1,
                            2,
                            GraphQLError("Test 3"),
                            4,
                            5,
                            GraphQLError("Test 6"),
                            7,
                        ],
                    ),
                    "nullableField": lambda _parent, _fa: constant(None),
                    "nonNullField": lambda _parent, _fa: constant(42),
                    "errorField": lambda _parent, _fa: lambda_(
                        None,
                        lambda _: _raise(GraphQLError("Field error")),
                    ),
                    "nestedError": lambda _parent, _fa: constant({"id": 1}),
                    "multipleErrors": lambda _parent, _fa: lambda_(
                        None,
                        lambda _: [
                            GraphQLError("Error A"),
                            2,
                            GraphQLError("Error C"),
                        ],
                    ),
                },
            },
            "Thing": {
                "plans": {
                    "id": lambda parent_step, _fa: parent_step,
                    "throw": lambda _parent, _fa: lambda_(
                        None,
                        lambda _: _raise(Exception("ERROR")),
                    ),
                },
            },
            "OtherThing": {
                "plans": {
                    "id": lambda parent_step, _fa: parent_step,
                },
            },
        },
    )


def _raise(e):
    """Helper to raise an exception inside a lambda."""
    raise e


# --- Test: nullable field returning null ---

@pytest.mark.asyncio
async def test_nullable_field_returns_null():
    """A nullable field that resolves to null should return null without errors."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="{ nullableField }",
    )
    assert result.errors is None
    assert result.data == {"nullableField": None}


# --- Test: non-null field returning value ---

@pytest.mark.asyncio
async def test_non_null_field_returns_value():
    """A non-null field that resolves to a value should return that value."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="{ nonNullField }",
    )
    assert result.errors is None
    assert result.data == {"nonNullField": 42}


# --- Test: error in a nullable field ---

@pytest.mark.asyncio
async def test_error_in_nullable_field():
    """An error in a nullable field should return null and add to errors list."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="{ errorField }",
    )
    assert result.errors is not None
    assert len(result.errors) == 1
    assert result.errors[0].message == "Field error"
    assert result.errors[0].path == ["errorField"]
    assert result.data == {"errorField": None}


# --- Test: errors inside lists ---

@pytest.mark.asyncio
async def test_errors_inside_lists():
    """Errors at specific positions in a list should become null with errors reported."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="{ listContainingErrors }",
    )
    assert result.errors is not None
    assert len(result.errors) == 2
    assert result.errors[0].message == "Test 3"
    assert result.errors[0].path == ["listContainingErrors", 2]
    assert result.errors[1].message == "Test 6"
    assert result.errors[1].path == ["listContainingErrors", 5]
    assert result.data == {
        "listContainingErrors": [1, 2, None, 4, 5, None, 7],
    }


# --- Test: multiple errors in a list ---

@pytest.mark.asyncio
async def test_multiple_errors_in_list():
    """Multiple error entries in a list should all be reported."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="{ multipleErrors }",
    )
    assert result.errors is not None
    assert len(result.errors) == 2
    assert result.errors[0].message == "Error A"
    assert result.errors[0].path == ["multipleErrors", 0]
    assert result.errors[1].message == "Error C"
    assert result.errors[1].path == ["multipleErrors", 2]
    assert result.data == {"multipleErrors": [None, 2, None]}


# --- Test: error in nested object field ---

@pytest.mark.asyncio
async def test_error_in_nested_field():
    """An error in a nested object's field should null that field and report error."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="""
            {
                list {
                    id
                    throw
                }
            }
        """,
    )
    assert result.data is not None
    assert result.data["list"] is not None
    assert len(result.data["list"]) == 2
    # throw field should be null due to error
    assert result.data["list"][0]["throw"] is None
    assert result.data["list"][1]["throw"] is None
    assert result.data["list"][0]["id"] == 1
    assert result.data["list"][1]["id"] == 2
    # Errors should be reported
    assert result.errors is not None
    assert len(result.errors) == 2
    assert result.errors[0].message == "ERROR"
    assert result.errors[1].message == "ERROR"


# --- Test: list with simple constant values ---

@pytest.mark.asyncio
async def test_list_of_constants():
    """A list of constant values should return correctly."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="{ list { id } }",
    )
    assert result.errors is None
    assert result.data == {
        "list": [{"id": 1}, {"id": 2}],
    }


# --- Test: error and valid data in same query ---

@pytest.mark.asyncio
async def test_error_and_valid_data_in_same_query():
    """A query with both erroring and valid fields should return both."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="""
            {
                nonNullField
                errorField
            }
        """,
    )
    assert result.errors is not None
    assert len(result.errors) == 1
    assert result.errors[0].message == "Field error"
    assert result.data is not None
    assert result.data["nonNullField"] == 42
    assert result.data["errorField"] is None
