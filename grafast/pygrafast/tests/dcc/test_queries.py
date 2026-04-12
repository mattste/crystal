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


# Start with just the 'friends' fixture as the first target
@pytest.mark.asyncio
async def test_friends_fixture(dcc_base_args):
    """Execute friends.test.graphql and compare to friends.json5."""
    graphql_file = FIXTURES_DIR / "friends.test.graphql"
    if not graphql_file.exists():
        pytest.skip("Fixture file not found")

    source = graphql_file.read_text()
    expected = load_json5_fixture("friends")
    assert expected is not None, "Expected .json5 fixture not found"

    result = await grafast(
        schema=dcc_base_args["schema"],
        source=source,
        context_value=dcc_base_args["context_value"],
    )

    assert result.errors is None, f"Unexpected errors: {result.errors}"
    assert result.data == expected
