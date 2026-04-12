"""DCC integration test runner.

Reads .test.graphql files and compares execution results against .json5 snapshots,
using the same test fixtures as the TypeScript grafast tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import json5
import pytest

from pygrafast import grafast

# Path to the shared TS test fixtures
FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "grafast"
    / "__tests__"
    / "dcc"
    / "queries"
)

SUFFIX = ".test.graphql"


def discover_test_cases() -> list[tuple[str, Path]]:
    """Discover all .test.graphql fixture files."""
    if not FIXTURES_DIR.exists():
        return []
    files = sorted(FIXTURES_DIR.glob(f"*{SUFFIX}"))
    return [(f.stem.removesuffix(".test"), f) for f in files]


# Non-incremental fixtures that we target for parity
NON_INCREMENTAL_FIXTURES = {
    "friends",
    "friends-of-friends",
    "friends-connection",
    "friendsConnection",
    "friendsConnection.2",
    "friends-connection-before-after",
    "items",
    "favourite-items",
    "favourite-items-and-floor",
    "floor",
    "floor-minimal",
    "floor-stock-minimum",
    "npc-friends",
    "npc-friends-different-count",
    "active-crawler-items-connection",
    "active-crawler-items-connection-page2",
    "active-crawler-items-connection-reverse",
    "item-query",
    "item-query-minimum",
    "item-lootbox",
    "item-lootbox-minimum",
    "broken-item",
    "missing-plan",
    "missing-plan-2",
}


def load_json5_fixture(base_name: str) -> dict | None:
    """Load the expected .json5 result for a test case."""
    json5_path = FIXTURES_DIR / f"{base_name}.json5"
    if not json5_path.exists():
        return None
    text = json5_path.read_text()
    return json5.loads(text)


@pytest.fixture(scope="module")
def dcc_base_args():
    """Create the DCC schema and context, equivalent to makeBaseArgs()."""
    from .dcc_schema import make_base_args
    return make_base_args()


def get_non_incremental_cases() -> list[tuple[str, Path]]:
    """Get test cases that don't require incremental delivery."""
    all_cases = discover_test_cases()
    result = []
    for name, path in all_cases:
        source = path.read_text()
        # Skip tests with @incremental directive (defer/stream)
        if "@incremental" in source:
            continue
        result.append((name, path))
    return result


@pytest.mark.parametrize(
    "base_name,graphql_file",
    get_non_incremental_cases(),
    ids=[name for name, _ in get_non_incremental_cases()],
)
@pytest.mark.asyncio
async def test_dcc_fixture(base_name: str, graphql_file: Path, dcc_base_args):
    """Execute a .test.graphql fixture and compare to .json5 snapshot."""
    source = graphql_file.read_text()

    from graphql import parse as gql_parse
    from graphql.language import OperationType

    document = gql_parse(source)
    operations = [d for d in document.definitions
                  if hasattr(d, 'operation')]

    # Use the first operation
    op = operations[0]
    operation_name = op.name.value if op.name else None

    # Extract variable values from @variables directive
    variable_values: dict[str, Any] = {}
    expect_error = False
    if op.directives:
        for directive in op.directives:
            if directive.name.value == "variables":
                for arg in directive.arguments or []:
                    if arg.name.value == "values":
                        from graphql.utilities import value_from_ast_untyped
                        variable_values = value_from_ast_untyped(arg.value)
            if directive.name.value == "expectError":
                expect_error = True

    result = await grafast(
        schema=dcc_base_args["schema"],
        source=source,
        context_value=dcc_base_args["context_value"],
        variable_values=variable_values,
        operation_name=operation_name,
    )

    expected = load_json5_fixture(base_name)
    if expected is None:
        pytest.skip(f"No .json5 fixture for {base_name}")

    if expect_error:
        assert result.errors is not None
    else:
        assert result.errors is None, f"Unexpected errors: {result.errors}"
        assert result.data == expected
