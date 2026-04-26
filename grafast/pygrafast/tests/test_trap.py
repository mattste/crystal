"""Trap tests - port of trap-test.ts.

Tests the trap(), assert_not_null(), and inhibit_on_null() mechanisms
for handling errors and nulls in the execution plan.
"""

import pytest

from pygrafast import grafast, make_grafast_schema
from pygrafast.steps import (
    TRAP_ERROR,
    assert_not_null,
    constant,
    lambda_,
    list_,
    trap,
)


def _make_schema():
    """Build the test schema with trap-based error handling.

    Port of the TS makeSchema() that uses assertNotNull and trap
    to convert errors into nulls, empty lists, or pass-through objects.
    """

    def plan_unhandled_error(_parent, field_args):
        step = field_args.get_raw("setNullToError")
        return assert_not_null(step, "Null!")

    def plan_error_to_null(_parent, field_args):
        step = field_args.get_raw("setNullToError")
        asserted = assert_not_null(step, "Null!")
        return trap(asserted, TRAP_ERROR, {"valueForError": "NULL"})

    def plan_error_to_empty_list(_parent, field_args):
        step = field_args.get_raw("setNullToError")
        asserted = assert_not_null(step, "Null!")
        listed = list_([asserted])
        return trap(listed, TRAP_ERROR, {"valueForError": "EMPTY_LIST"})

    def plan_error_to_error(_parent, field_args):
        step = field_args.get_raw("setNullToError")
        asserted = assert_not_null(step, "Null!")
        derived = lambda_(asserted, lambda _: None, is_sync_and_safe=True)
        return trap(derived, TRAP_ERROR, {"valueForError": "PASS_THROUGH"})

    def plan_my_side_effect(_parent, _field_args):
        """Side effect that throws, trapped and then overridden with a constant."""
        step = lambda_(None, lambda _: _raise(Exception("Test")))
        trapped = trap(step, TRAP_ERROR, {"valueForError": "PASS_THROUGH"})
        return lambda_(trapped, lambda _: 1)

    def plan_my_side_effect_error(_parent, _field_args):
        """Side effect that throws with custom attributes, trapped with pass-through."""
        err = Exception("Test 2")
        err.errcode = 42  # type: ignore[attr-defined]
        err.detail = "Goodbye, and thanks for all the fish!"  # type: ignore[attr-defined]
        step = lambda_(None, lambda _: _raise(err))
        trapped = trap(step, TRAP_ERROR, {"valueForError": "PASS_THROUGH"})
        return trapped

    return make_grafast_schema(
        type_defs="""
            type Error {
                message: String
            }
            type Query {
                unhandledError(setNullToError: Int): Int
                errorToNull(setNullToError: Int): Int
                errorToEmptyList(setNullToError: Int): [Int]
                errorToError(setNullToError: Int): Error
                mySideEffect: Int
                mySideEffectError: MySideEffectError
            }
            type MySideEffectError {
                message: String!
                errcode: Int!
                detail: String!
            }
        """,
        objects={
            "Query": {
                "plans": {
                    "unhandledError": plan_unhandled_error,
                    "errorToNull": plan_error_to_null,
                    "errorToEmptyList": plan_error_to_empty_list,
                    "errorToError": plan_error_to_error,
                    "mySideEffect": plan_my_side_effect,
                    "mySideEffectError": plan_my_side_effect_error,
                },
            },
        },
    )


def _raise(e):
    """Helper to raise an exception inside a lambda."""
    raise e


# --- Test 1: Schema works - unhandled error propagates ---

@pytest.mark.asyncio
async def test_unhandled_error_propagates():
    """assertNotNull should propagate as a GraphQL error when the value is null,
    but pass through when the value is non-null."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="""
            query Q {
                nonError: unhandledError(setNullToError: 2)
                error: unhandledError(setNullToError: null)
            }
        """,
        variable_values={},
    )
    assert result.errors is not None
    assert len(result.errors) == 1
    assert result.errors[0].path == ["error"]
    assert result.errors[0].message == "Null!"
    assert result.data == {"nonError": 2, "error": None}


# --- Test 2: Trap error to null ---

@pytest.mark.asyncio
async def test_trap_error_to_null():
    """trap($step, TRAP_ERROR, {valueForError: 'NULL'}) should convert errors to null."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="""
            query Q {
                nonError: errorToNull(setNullToError: 2)
                error: errorToNull(setNullToError: null)
            }
        """,
        variable_values={},
    )
    assert result.errors is None
    assert result.data == {"nonError": 2, "error": None}


# --- Test 3: Trap error to empty list ---

@pytest.mark.asyncio
async def test_trap_error_to_empty_list():
    """trap($step, TRAP_ERROR, {valueForError: 'EMPTY_LIST'}) should convert
    errors to an empty list."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="""
            query Q {
                nonError: errorToEmptyList(setNullToError: 2)
                error: errorToEmptyList(setNullToError: null)
            }
        """,
        variable_values={},
    )
    assert result.errors is None
    assert result.data == {"nonError": [2], "error": []}


# --- Test 4: Trap error to error object (pass-through) ---

@pytest.mark.asyncio
async def test_trap_error_to_error_object():
    """trap($step, TRAP_ERROR, {valueForError: 'PASS_THROUGH'}) should convert
    the error into an object whose properties (like .message) can be queried."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="""
            query Q {
                nonError: errorToError(setNullToError: 2) {
                    message
                }
                error: errorToError(setNullToError: null) {
                    message
                }
            }
        """,
        variable_values={},
    )
    assert result.errors is None
    assert result.data == {
        "nonError": None,
        "error": {"message": "Null!"},
    }


# --- Test 5: Trap side effect error then override ---

@pytest.mark.asyncio
async def test_trap_side_effect_error():
    """Trapping an error from a side effect and overriding with a constant
    should produce the constant."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="query withSideEffects { mySideEffect }",
    )
    assert result.data == {"mySideEffect": 1}
    assert result.errors is None


# --- Test 6: Trap side effect error with pass-through for object fields ---

@pytest.mark.asyncio
async def test_trap_side_effect_error_pass_through():
    """Trapping a side effect error with PASS_THROUGH allows querying the
    error's custom properties (message, errcode, detail)."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="""
            query withSideEffects {
                mySideEffectError {
                    message
                    errcode
                    detail
                }
            }
        """,
    )
    assert result.data == {
        "mySideEffectError": {
            "message": "Test 2",
            "errcode": 42,
            "detail": "Goodbye, and thanks for all the fish!",
        },
    }
    assert result.errors is None


# --- Test 7: Non-null field with valid value passes through assert_not_null ---

@pytest.mark.asyncio
async def test_assert_not_null_passes_with_value():
    """When assertNotNull receives a non-null value, it passes through unchanged."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="{ unhandledError(setNullToError: 42) }",
    )
    assert result.errors is None
    assert result.data == {"unhandledError": 42}


# --- Test 8: Multiple fields with mixed trap behavior ---

@pytest.mark.asyncio
async def test_mixed_trap_and_unhandled():
    """A query combining trapped and untrapped errors should correctly handle each."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="""
            query Q {
                trapped: errorToNull(setNullToError: null)
                untrapped: unhandledError(setNullToError: null)
                valid: unhandledError(setNullToError: 5)
            }
        """,
    )
    assert result.errors is not None
    assert len(result.errors) == 1
    assert result.errors[0].path == ["untrapped"]
    assert result.errors[0].message == "Null!"
    assert result.data is not None
    assert result.data["trapped"] is None
    assert result.data["untrapped"] is None
    assert result.data["valid"] == 5
