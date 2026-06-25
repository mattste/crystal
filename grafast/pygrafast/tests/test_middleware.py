"""Port of grafast/__tests__/middleware-test.ts

Tests the middleware system that allows intercepting various phases of the
grafast execution pipeline: execute, parseAndValidate, and
establishOperationPlan.  Middleware can modify arguments before a phase runs,
inspect or alter results after, add extensions to the response, short-circuit
execution, and compose in a predictable order.
"""

import json

import pytest

from pygrafast import GrafastResult, Middleware, MiddlewareEvent, grafast, make_grafast_schema
from pygrafast.steps import constant


# ---------------------------------------------------------------------------
# Shared test schema
# ---------------------------------------------------------------------------

def _make_schema():
    """Build a minimal schema with a single ``hello`` field."""
    return make_grafast_schema(
        type_defs="""
            type Query {
                hello: String!
            }
        """,
        objects={
            "Query": {
                "plans": {
                    "hello": lambda _parent, _args: constant("world"),
                },
            },
        },
    )


# ---------------------------------------------------------------------------
# Test 1: execute middleware runs in order (before / after)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_middleware_runs_in_order():
    """Mirrors the TS test: 'runs grafast execute middleware in order'.

    Registers an execute-phase middleware that:
    - records 'before' when entered
    - modifies context_value
    - records 'after' after the pipeline completes
    - attaches a context snapshot to result.extensions
    """
    calls: list[str] = []

    async def execute_mw(event: MiddlewareEvent, next_fn):
        calls.append("before")
        # Modify context_value in the args (mirrors the TS test)
        event.args["context_value"] = {"middleware": "before"}
        result = await next_fn()
        calls.append("after")
        # Attach extensions (mirrors TS: r.extensions.contextSnapshot = ...)
        if result.extensions is None:
            result.extensions = {}
        result.extensions["contextSnapshot"] = json.dumps(
            event.args["context_value"]
        )
        return result

    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="{ hello }",
        middleware=Middleware.from_dict({"execute": execute_mw}),
    )

    assert result.errors is None
    assert result.data == {"hello": "world"}
    assert result.extensions == {
        "contextSnapshot": json.dumps({"middleware": "before"}),
    }
    assert calls == ["before", "after"]


# ---------------------------------------------------------------------------
# Test 2: middleware can add extensions to the result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_middleware_adds_extensions():
    """Middleware that adds arbitrary extension data to the response."""

    async def add_timing(event: MiddlewareEvent, next_fn):
        import time

        start = time.monotonic()
        result = await next_fn()
        elapsed = time.monotonic() - start
        if result.extensions is None:
            result.extensions = {}
        result.extensions["timing_ms"] = round(elapsed * 1000, 2)
        return result

    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="{ hello }",
        middleware=Middleware.from_dict({"execute": add_timing}),
    )

    assert result.errors is None
    assert result.data == {"hello": "world"}
    assert "timing_ms" in result.extensions
    assert isinstance(result.extensions["timing_ms"], float)


# ---------------------------------------------------------------------------
# Test 3: middleware can short-circuit execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_middleware_short_circuits_execution():
    """Middleware that returns a canned result without calling next()."""

    async def block_all(event: MiddlewareEvent, next_fn):
        # Never call next_fn -- short-circuit
        return GrafastResult(
            data=None,
            errors=[Exception("blocked by middleware")],
        )

    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="{ hello }",
        middleware=Middleware.from_dict({"execute": block_all}),
    )

    assert result.data is None
    assert len(result.errors) == 1
    assert str(result.errors[0]) == "blocked by middleware"


# ---------------------------------------------------------------------------
# Test 4: multiple middleware compose in registration order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_middleware_compose_in_order():
    """Two execute middlewares run in registration order (onion model)."""
    calls: list[str] = []

    async def mw_outer(event: MiddlewareEvent, next_fn):
        calls.append("outer-before")
        result = await next_fn()
        calls.append("outer-after")
        return result

    async def mw_inner(event: MiddlewareEvent, next_fn):
        calls.append("inner-before")
        result = await next_fn()
        calls.append("inner-after")
        return result

    mw = Middleware()
    mw.register("execute", mw_outer)
    mw.register("execute", mw_inner)

    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="{ hello }",
        middleware=mw,
    )

    assert result.errors is None
    assert result.data == {"hello": "world"}
    assert calls == [
        "outer-before",
        "inner-before",
        "inner-after",
        "outer-after",
    ]


# ---------------------------------------------------------------------------
# Test 5: middleware on parseAndValidate phase
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_and_validate_middleware():
    """Middleware intercepts the parseAndValidate phase.

    We verify that the middleware is invoked and can observe / alter the
    parse result.
    """
    parse_called = {"count": 0}

    def pv_mw(event: MiddlewareEvent, next_fn):
        parse_called["count"] += 1
        result = next_fn()
        return result

    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="{ hello }",
        middleware=Middleware.from_dict({"parseAndValidate": pv_mw}),
    )

    assert result.errors is None
    assert result.data == {"hello": "world"}
    assert parse_called["count"] == 1


# ---------------------------------------------------------------------------
# Test 6: parseAndValidate middleware can reject a query
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_and_validate_middleware_rejects_query():
    """parseAndValidate middleware can replace the validation result to
    reject queries (e.g., a query-complexity limiter).
    """

    def reject_mw(event: MiddlewareEvent, next_fn):
        # Still parse/validate normally ...
        document, errors = next_fn()
        # ... then unconditionally add a validation error
        errors = list(errors) if errors else []
        errors.append(Exception("query too complex"))
        return document, errors

    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="{ hello }",
        middleware=Middleware.from_dict({"parseAndValidate": reject_mw}),
    )

    assert result.data is None or result.errors is not None
    assert any("query too complex" in str(e) for e in result.errors)


# ---------------------------------------------------------------------------
# Test 7: middleware dict shorthand
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_middleware_dict_shorthand():
    """grafast() accepts a plain dict as middleware for convenience."""
    called = {"execute": False}

    async def mw(event: MiddlewareEvent, next_fn):
        called["execute"] = True
        return await next_fn()

    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="{ hello }",
        middleware={"execute": mw},
    )

    assert result.errors is None
    assert result.data == {"hello": "world"}
    assert called["execute"] is True


# ---------------------------------------------------------------------------
# Test 8: no middleware -- default behaviour is unchanged
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_middleware_default_behaviour():
    """Without middleware, grafast() behaves exactly as before."""
    schema = _make_schema()
    result = await grafast(
        schema=schema,
        source="{ hello }",
    )

    assert result.errors is None
    assert result.data == {"hello": "world"}
    assert result.extensions is None
