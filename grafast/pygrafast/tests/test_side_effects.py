"""Side effects and mutation tests - port of sideEffectsCancelFollowingSteps-test.ts.

Tests side effect ordering, error propagation from side effects,
and mutation execution through the pygrafast engine.
"""

import pytest

from pygrafast import grafast, make_grafast_schema
from pygrafast.steps import constant, lambda_, side_effect
from pygrafast.steps.context_step import context


# ---------------------------------------------------------------------------
# Test 1: Basic mutation execution with side effects
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_basic_mutation_execution():
    """A mutation with a single side effect should execute and return result."""
    schema = make_grafast_schema(
        type_defs="""
            type Query {
                dummy: Int
            }
            type Mutation {
                increment: Int
            }
        """,
        objects={
            "Query": {
                "plans": {
                    "dummy": lambda _p, _fa: constant(0),
                },
            },
            "Mutation": {
                "plans": {
                    "increment": _increment_resolver,
                },
            },
        },
    )

    result = await grafast(
        schema=schema,
        source="mutation { increment }",
        context_value={"counter": 0},
    )
    assert result.errors is None
    assert result.data == {"increment": 1}


def _increment_resolver(_parent, _fa):
    ctx_step = context()
    side_effect(ctx_step, lambda ctx: _do_increment(ctx))
    return ctx_step.get("counter")


def _do_increment(ctx):
    ctx["counter"] = ctx.get("counter", 0) + 1


# ---------------------------------------------------------------------------
# Test 2: Side effects execute in order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_side_effects_execute_in_order():
    """Multiple side effects should execute sequentially in declaration order."""
    execution_log = []

    def make_resolver():
        def resolver(_parent, _fa):
            ctx_step = context()
            side_effect(ctx_step, lambda ctx: _log_and_set(ctx, execution_log, "first", 10))
            side_effect(ctx_step, lambda ctx: _log_and_set(ctx, execution_log, "second", 20))
            side_effect(ctx_step, lambda ctx: _log_and_set(ctx, execution_log, "third", 30))
            return ctx_step.get("value")
        return resolver

    schema = make_grafast_schema(
        type_defs="""
            type Query { dummy: Int }
            type Mutation { ordered: Int }
        """,
        objects={
            "Query": {"plans": {"dummy": lambda _p, _fa: constant(0)}},
            "Mutation": {"plans": {"ordered": make_resolver()}},
        },
    )

    ctx = {"value": 0}
    result = await grafast(
        schema=schema,
        source="mutation { ordered }",
        context_value=ctx,
    )
    assert result.errors is None
    # The last side effect sets value to 30
    assert result.data == {"ordered": 30}
    assert execution_log == ["first", "second", "third"]


def _log_and_set(ctx, log, name, value):
    log.append(name)
    ctx["value"] = value


# ---------------------------------------------------------------------------
# Test 3: Error in side effect cancels following steps (the main TS test)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_error_cancels_following_side_effects():
    """If a side effect errors, subsequent side effects should not execute.

    This is a direct port of the TypeScript test from
    sideEffectsCancelFollowingSteps-test.ts.
    """
    def test_resolver(_parent, _fa):
        ctx_step = context()
        side_effect(ctx_step, lambda ctx: _set_number(ctx, 3))
        side_effect(ctx_step, lambda ctx: _inc_number(ctx))
        side_effect(ctx_step, lambda _ctx: _raise_error("Side effect 3 failed"))
        # The following two effects should NOT execute
        side_effect(ctx_step, lambda ctx: _inc_number(ctx))
        side_effect(ctx_step, lambda ctx: _inc_number(ctx))
        return ctx_step.get("number")

    schema = make_grafast_schema(
        type_defs="""
            type Query { test: Int }
            type Mutation { test: Int }
        """,
        objects={
            "Query": {"plans": {"test": test_resolver}},
            "Mutation": {"plans": {"test": test_resolver}},
        },
    )

    ctx_value = {}
    result = await grafast(
        schema=schema,
        source="mutation M { test }",
        context_value=ctx_value,
    )

    # The field should be null due to the error
    assert result.data == {"test": None}

    # There should be one error
    assert result.errors is not None
    assert len(result.errors) == 1
    assert result.errors[0].message == "Side effect 3 failed"
    assert result.errors[0].path == ["test"]

    # context.number should be 4 (3 + 1 increment, then error stops further increments)
    assert ctx_value["number"] == 4


def _set_number(ctx, value):
    ctx["number"] = value


def _inc_number(ctx):
    ctx["number"] = ctx.get("number", 0) + 1


def _raise_error(msg):
    raise Exception(msg)


# ---------------------------------------------------------------------------
# Test 4: Side effects with no errors should all execute
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_side_effects_run_when_no_error():
    """When no side effect raises, all should execute and the final value returned."""
    def resolver(_parent, _fa):
        ctx_step = context()
        side_effect(ctx_step, lambda ctx: _set_number(ctx, 1))
        side_effect(ctx_step, lambda ctx: _inc_number(ctx))
        side_effect(ctx_step, lambda ctx: _inc_number(ctx))
        side_effect(ctx_step, lambda ctx: _inc_number(ctx))
        return ctx_step.get("number")

    schema = make_grafast_schema(
        type_defs="""
            type Query { dummy: Int }
            type Mutation { count: Int }
        """,
        objects={
            "Query": {"plans": {"dummy": lambda _p, _fa: constant(0)}},
            "Mutation": {"plans": {"count": resolver}},
        },
    )

    ctx = {}
    result = await grafast(
        schema=schema,
        source="mutation { count }",
        context_value=ctx,
    )
    assert result.errors is None
    assert result.data == {"count": 4}
    assert ctx["number"] == 4


# ---------------------------------------------------------------------------
# Test 5: First side effect errors - all subsequent are cancelled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_first_side_effect_error_cancels_all():
    """If the first side effect errors, none of the subsequent should run."""
    def resolver(_parent, _fa):
        ctx_step = context()
        side_effect(ctx_step, lambda _ctx: _raise_error("First failed"))
        side_effect(ctx_step, lambda ctx: _set_number(ctx, 100))
        side_effect(ctx_step, lambda ctx: _set_number(ctx, 200))
        return ctx_step.get("number")

    schema = make_grafast_schema(
        type_defs="""
            type Query { dummy: Int }
            type Mutation { val: Int }
        """,
        objects={
            "Query": {"plans": {"dummy": lambda _p, _fa: constant(0)}},
            "Mutation": {"plans": {"val": resolver}},
        },
    )

    ctx = {}
    result = await grafast(
        schema=schema,
        source="mutation { val }",
        context_value=ctx,
    )
    assert result.data == {"val": None}
    assert result.errors is not None
    assert len(result.errors) == 1
    assert result.errors[0].message == "First failed"
    # number should NOT be set since first side effect failed
    assert "number" not in ctx


# ---------------------------------------------------------------------------
# Test 6: Multiple mutation fields execute independently
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_mutation_fields():
    """Multiple mutation fields should each execute their side effects."""
    def resolver_a(_parent, _fa):
        ctx_step = context()
        side_effect(ctx_step, lambda ctx: ctx.__setitem__("a", 1))
        return ctx_step.get("a")

    def resolver_b(_parent, _fa):
        ctx_step = context()
        side_effect(ctx_step, lambda ctx: ctx.__setitem__("b", 2))
        return ctx_step.get("b")

    schema = make_grafast_schema(
        type_defs="""
            type Query { dummy: Int }
            type Mutation {
                setA: Int
                setB: Int
            }
        """,
        objects={
            "Query": {"plans": {"dummy": lambda _p, _fa: constant(0)}},
            "Mutation": {
                "plans": {
                    "setA": resolver_a,
                    "setB": resolver_b,
                },
            },
        },
    )

    ctx = {}
    result = await grafast(
        schema=schema,
        source="mutation { setA setB }",
        context_value=ctx,
    )
    assert result.errors is None
    assert result.data == {"setA": 1, "setB": 2}
    assert ctx["a"] == 1
    assert ctx["b"] == 2


# ---------------------------------------------------------------------------
# Test 7: Side effect with lambda-style return value
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_side_effect_return_value():
    """A side_effect step returns the value from its callback, which
    can be used by downstream steps."""
    def resolver(_parent, _fa):
        ctx_step = context()
        result_step = side_effect(ctx_step, lambda ctx: _multiply(ctx))
        return result_step

    schema = make_grafast_schema(
        type_defs="""
            type Query { dummy: Int }
            type Mutation { doubled: Int }
        """,
        objects={
            "Query": {"plans": {"dummy": lambda _p, _fa: constant(0)}},
            "Mutation": {"plans": {"doubled": resolver}},
        },
    )

    result = await grafast(
        schema=schema,
        source="mutation { doubled }",
        context_value={"input": 21},
    )
    assert result.errors is None
    assert result.data == {"doubled": 42}


def _multiply(ctx):
    return ctx.get("input", 0) * 2


# ---------------------------------------------------------------------------
# Test 8: Query with side effects also works (same as mutation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_side_effects_in_query():
    """Side effects should also work in queries (though mutations are typical)."""
    def resolver(_parent, _fa):
        ctx_step = context()
        side_effect(ctx_step, lambda ctx: ctx.__setitem__("touched", True))
        return ctx_step.get("touched")

    schema = make_grafast_schema(
        type_defs="""
            type Query { touch: Boolean }
        """,
        objects={
            "Query": {"plans": {"touch": resolver}},
        },
    )

    ctx = {}
    result = await grafast(
        schema=schema,
        source="{ touch }",
        context_value=ctx,
    )
    assert result.errors is None
    assert result.data == {"touch": True}
    assert ctx["touched"] is True
