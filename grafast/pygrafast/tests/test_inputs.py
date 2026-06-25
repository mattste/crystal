"""Port of grafast/__tests__/inputs-test.ts

Tests that pygrafast correctly handles various input types:
- Scalar input arguments (Int, String, Boolean, Float, ID)
- Enum input arguments
- Input object arguments
- Default argument values
- Variable values passed as arguments
- List inputs with nullable/non-nullable combinations
- Null values for nullable inputs
- Coercion of input values
"""

import pytest

from pygrafast import grafast, make_grafast_schema


# ---------------------------------------------------------------------------
# Schema builders
# ---------------------------------------------------------------------------

def _make_list_schema():
    """Build a schema with list-of-string fields matching the TS test."""
    return make_grafast_schema(
        type_defs="""
            type Query {
                echoListOfString(in: [String]): [String]
                echoListOfNonNullableString(in: [String!]): [String!]
                echoNonNullableListOfNonNullableString(in: [String!]!): [String!]!
                echoNonNullableListOfString(in: [String]!): [String]!
            }
        """,
        objects={
            "Query": {
                "plans": {
                    "echoListOfString": lambda _, args: args.get_raw("in"),
                    "echoListOfNonNullableString": lambda _, args: args.get_raw("in"),
                    "echoNonNullableListOfString": lambda _, args: args.get_raw("in"),
                    "echoNonNullableListOfNonNullableString": lambda _, args: args.get_raw("in"),
                },
            },
        },
    )


def _make_scalar_schema():
    """Build a schema testing all scalar input types."""
    return make_grafast_schema(
        type_defs="""
            type Query {
                echoInt(value: Int): Int
                echoString(value: String): String
                echoBoolean(value: Boolean): Boolean
                echoFloat(value: Float): Float
                echoID(value: ID): ID
            }
        """,
        objects={
            "Query": {
                "plans": {
                    "echoInt": lambda _, args: args.get_raw("value"),
                    "echoString": lambda _, args: args.get_raw("value"),
                    "echoBoolean": lambda _, args: args.get_raw("value"),
                    "echoFloat": lambda _, args: args.get_raw("value"),
                    "echoID": lambda _, args: args.get_raw("value"),
                },
            },
        },
    )


def _make_enum_schema():
    """Build a schema testing enum input arguments."""
    return make_grafast_schema(
        type_defs="""
            enum Color {
                RED
                GREEN
                BLUE
            }
            type Query {
                echoColor(color: Color): String
            }
        """,
        objects={
            "Query": {
                "plans": {
                    "echoColor": lambda _, args: args.get_raw("color"),
                },
            },
        },
    )


def _make_input_object_schema():
    """Build a schema testing input object arguments.

    Uses access() to extract individual fields from the input object,
    verifying that input objects are properly decomposed.
    """
    from pygrafast.steps.access import access
    from pygrafast.steps.lambda_step import lambda_

    def _plan_echo_name(_, args):
        input_step = args.get_raw("input")
        return lambda_(input_step, lambda v: v["name"] if v else None)

    def _plan_echo_age(_, args):
        input_step = args.get_raw("input")
        return lambda_(input_step, lambda v: v.get("age") if v else None)

    return make_grafast_schema(
        type_defs="""
            input UserInput {
                name: String!
                age: Int
            }
            type Query {
                echoUserName(input: UserInput): String
                echoUserAge(input: UserInput): Int
            }
        """,
        objects={
            "Query": {
                "plans": {
                    "echoUserName": _plan_echo_name,
                    "echoUserAge": _plan_echo_age,
                },
            },
        },
    )


def _make_default_args_schema():
    """Build a schema testing default argument values."""
    return make_grafast_schema(
        type_defs="""
            type Query {
                greet(name: String = "World"): String
                count(n: Int = 42): Int
                flag(on: Boolean = true): Boolean
            }
        """,
        objects={
            "Query": {
                "plans": {
                    "greet": lambda _, args: args.get_raw("name"),
                    "count": lambda _, args: args.get_raw("n"),
                    "flag": lambda _, args: args.get_raw("on"),
                },
            },
        },
    )


# ---------------------------------------------------------------------------
# Test 1: List inputs with matching types (direct port from TS)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_inputs_matching_types():
    """Executes with matching variable types -- direct port of the TS test."""
    schema = _make_list_schema()
    source = """
        query Q(
            $los1: [String]
            $los2: [String]
            $los3: [String]
            $los4: [String]
            $lonns1: [String!]
            $lonns2: [String!]
            $nnlos1: [String]!
            $nnlos2: [String]!
            $nnlos3: [String]!
            $nnlonns1: [String!]!
        ) {
            los1: echoListOfString(in: $los1)
            los2: echoListOfString(in: $los2)
            los3: echoListOfString(in: $los3)
            los4: echoListOfString(in: $los4)
            lonns1: echoListOfNonNullableString(in: $lonns1)
            lonns2: echoListOfNonNullableString(in: $lonns2)
            nnlos1: echoNonNullableListOfString(in: $nnlos1)
            nnlos2: echoNonNullableListOfString(in: $nnlos2)
            nnlos3: echoNonNullableListOfString(in: $nnlos3)
            nnlonns1: echoNonNullableListOfNonNullableString(in: $nnlonns1)
        }
    """
    variable_values = {
        "los1": ["1", "2", "3"],
        "los2": [None, "2", None],
        "los3": [None, None, None],
        "los4": None,
        "lonns1": ["1", "2", "3"],
        "lonns2": None,
        "nnlos1": ["1", "2", "3"],
        "nnlos2": [None, "2", None],
        "nnlos3": [None, None, None],
        "nnlonns1": ["1", "2", "3"],
    }
    result = await grafast(
        schema=schema,
        source=source,
        variable_values=variable_values,
    )
    assert result.errors is None
    assert result.data == variable_values


# ---------------------------------------------------------------------------
# Test 2: List inputs with stricter inner type
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_inputs_stricter_inner_type():
    """Variables with [String!] passed to [String] fields."""
    schema = _make_list_schema()
    source = """
        query Q(
            $los1: [String!]
            $los4: [String!]
            $lonns1: [String!]
            $lonns2: [String!]
            $nnlos1: [String!]!
            $nnlonns1: [String!]!
        ) {
            los1: echoListOfString(in: $los1)
            los4: echoListOfString(in: $los4)
            lonns1: echoListOfNonNullableString(in: $lonns1)
            lonns2: echoListOfNonNullableString(in: $lonns2)
            nnlos1: echoNonNullableListOfString(in: $nnlos1)
            nnlonns1: echoNonNullableListOfNonNullableString(in: $nnlonns1)
        }
    """
    variable_values = {
        "los1": ["1", "2", "3"],
        "los4": None,
        "lonns1": ["1", "2", "3"],
        "lonns2": None,
        "nnlos1": ["1", "2", "3"],
        "nnlonns1": ["1", "2", "3"],
    }
    result = await grafast(
        schema=schema,
        source=source,
        variable_values=variable_values,
    )
    assert result.errors is None
    assert result.data == variable_values


# ---------------------------------------------------------------------------
# Test 3: Scalar input arguments with literal values
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scalar_literal_inputs():
    """Literal scalar values in query arguments are correctly coerced."""
    schema = _make_scalar_schema()
    result = await grafast(
        schema=schema,
        source="""
            query {
                echoInt(value: 42)
                echoString(value: "hello")
                echoBoolean(value: true)
                echoFloat(value: 3.14)
                echoID(value: "abc-123")
            }
        """,
    )
    assert result.errors is None
    assert result.data == {
        "echoInt": 42,
        "echoString": "hello",
        "echoBoolean": True,
        "echoFloat": 3.14,
        "echoID": "abc-123",
    }


# ---------------------------------------------------------------------------
# Test 4: Scalar input arguments with variables
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scalar_variable_inputs():
    """Variables are correctly resolved for all scalar types."""
    schema = _make_scalar_schema()
    result = await grafast(
        schema=schema,
        source="""
            query Q($i: Int, $s: String, $b: Boolean, $f: Float, $id: ID) {
                echoInt(value: $i)
                echoString(value: $s)
                echoBoolean(value: $b)
                echoFloat(value: $f)
                echoID(value: $id)
            }
        """,
        variable_values={
            "i": 99,
            "s": "world",
            "b": False,
            "f": 2.718,
            "id": "xyz-789",
        },
    )
    assert result.errors is None
    assert result.data == {
        "echoInt": 99,
        "echoString": "world",
        "echoBoolean": False,
        "echoFloat": 2.718,
        "echoID": "xyz-789",
    }


# ---------------------------------------------------------------------------
# Test 5: Null values for nullable inputs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_null_nullable_inputs():
    """Null values for nullable scalar arguments are handled."""
    schema = _make_scalar_schema()
    result = await grafast(
        schema=schema,
        source="""
            query Q($i: Int, $s: String) {
                echoInt(value: $i)
                echoString(value: $s)
            }
        """,
        variable_values={
            "i": None,
            "s": None,
        },
    )
    assert result.errors is None
    assert result.data == {
        "echoInt": None,
        "echoString": None,
    }


# ---------------------------------------------------------------------------
# Test 6: Default argument values
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_default_argument_values():
    """Arguments with defaults use the default when not provided."""
    schema = _make_default_args_schema()
    result = await grafast(
        schema=schema,
        source="""
            query {
                greet
                count
                flag
            }
        """,
    )
    assert result.errors is None
    assert result.data == {
        "greet": "World",
        "count": 42,
        "flag": True,
    }


# ---------------------------------------------------------------------------
# Test 7: Default argument values overridden by variables
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_default_args_overridden_by_variables():
    """When a variable is provided, it overrides the default."""
    schema = _make_default_args_schema()
    result = await grafast(
        schema=schema,
        source="""
            query Q($name: String, $n: Int) {
                greet(name: $name)
                count(n: $n)
            }
        """,
        variable_values={
            "name": "Alice",
            "n": 7,
        },
    )
    assert result.errors is None
    assert result.data == {
        "greet": "Alice",
        "count": 7,
    }


# ---------------------------------------------------------------------------
# Test 8: Enum input arguments
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enum_literal_input():
    """Enum values passed as literals are resolved correctly."""
    schema = _make_enum_schema()
    result = await grafast(
        schema=schema,
        source="""
            query {
                echoColor(color: RED)
            }
        """,
    )
    assert result.errors is None
    assert result.data == {
        "echoColor": "RED",
    }


# ---------------------------------------------------------------------------
# Test 9: Enum input via variable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enum_variable_input():
    """Enum values passed via variables are resolved correctly."""
    schema = _make_enum_schema()
    result = await grafast(
        schema=schema,
        source="""
            query Q($color: Color) {
                echoColor(color: $color)
            }
        """,
        variable_values={"color": "BLUE"},
    )
    assert result.errors is None
    assert result.data == {
        "echoColor": "BLUE",
    }


# ---------------------------------------------------------------------------
# Test 10: Input object argument with field extraction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_input_object_via_variable():
    """Input objects passed via variables are properly accessible in plan resolvers."""
    schema = _make_input_object_schema()
    result = await grafast(
        schema=schema,
        source="""
            query Q($input: UserInput) {
                echoUserName(input: $input)
                echoUserAge(input: $input)
            }
        """,
        variable_values={"input": {"name": "Alice", "age": 30}},
    )
    assert result.errors is None
    assert result.data == {
        "echoUserName": "Alice",
        "echoUserAge": 30,
    }
