"""Conformance test: @include and @skip directives.

Port of grafast/__tests__/conformance/include-test.ts.

Tests that pygrafast handles @include and @skip directives within abstract
position fragment spreads identically to graphql-core.
"""

import pytest

from .utils import assert_conformance, make_conformance_schema

schema = make_conformance_schema(
    """
    type Query implements SomeInterface {
        int: Int
        abstract: SomeInterface
    }

    interface SomeInterface {
        int: Int
    }
    """
)


class TestIncludeWithinAbstractPositionFragmentSpreads:
    """handles @include within abstract position fragment spreads"""

    source = """
        query ($include: Boolean!) {
            abstract {
                ... @include(if: $include) {
                    int
                }
            }
        }
    """

    @pytest.mark.asyncio
    async def test_include_true(self):
        await assert_conformance(schema, self.source, {"include": True})

    @pytest.mark.asyncio
    async def test_include_false(self):
        await assert_conformance(schema, self.source, {"include": False})


class TestSkipWithinAbstractPositionFragmentSpreads:
    """handles @skip within abstract position fragment spreads"""

    source = """
        query ($exclude: Boolean!) {
            abstract {
                ... @skip(if: $exclude) {
                    int
                }
            }
        }
    """

    @pytest.mark.asyncio
    async def test_exclude_true(self):
        await assert_conformance(schema, self.source, {"exclude": True})

    @pytest.mark.asyncio
    async def test_exclude_false(self):
        await assert_conformance(schema, self.source, {"exclude": False})
