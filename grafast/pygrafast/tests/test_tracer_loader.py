"""Tracer 2 RED: Object fields + LoadOne (crawler lookup)."""

import pytest

from pygrafast import grafast, make_grafast_schema
from pygrafast.steps import lambda_
from pygrafast.steps.access import access
from pygrafast.steps.load_one import load_one


# Mini in-memory database
CRAWLERS = [
    {"id": 101, "species": "Human", "name": "Carl"},
    {"id": 102, "species": "Cat", "name": "Princess Donut"},
    {"id": 103, "species": "Human", "name": "Katia"},
]


def batch_get_crawler_by_id(ids, _extra):
    return [next((c for c in CRAWLERS if c["id"] == id), None) for id in ids]


@pytest.mark.asyncio
async def test_crawler_by_id():
    """Query a single crawler by ID, returning object fields."""
    schema = make_grafast_schema(
        type_defs="""
            type Query {
                crawler(id: Int!): Crawler
            }
            type Crawler {
                id: Int!
                name: String!
                species: String
            }
        """,
        objects={
            "Query": {
                "plans": {
                    "crawler": lambda _parent, field_args: load_one(
                        field_args.get_raw("id"),
                        batch_get_crawler_by_id,
                    ),
                },
            },
        },
    )
    result = await grafast(
        schema=schema,
        source="{ crawler(id: 101) { id name species } }",
    )
    assert result.errors is None
    assert result.data == {
        "crawler": {"id": 101, "name": "Carl", "species": "Human"}
    }


@pytest.mark.asyncio
async def test_crawler_not_found():
    """Query a crawler that doesn't exist returns null."""
    schema = make_grafast_schema(
        type_defs="""
            type Query {
                crawler(id: Int!): Crawler
            }
            type Crawler {
                id: Int!
                name: String!
            }
        """,
        objects={
            "Query": {
                "plans": {
                    "crawler": lambda _parent, field_args: load_one(
                        field_args.get_raw("id"),
                        batch_get_crawler_by_id,
                    ),
                },
            },
        },
    )
    result = await grafast(
        schema=schema,
        source="{ crawler(id: 999) { id name } }",
    )
    assert result.errors is None
    assert result.data == {"crawler": None}


@pytest.mark.asyncio
async def test_nested_object_fields():
    """Query with nested object fields using access steps."""
    schema = make_grafast_schema(
        type_defs="""
            type Query {
                crawler(id: Int!): Crawler
            }
            type Crawler {
                id: Int!
                name: String!
            }
        """,
        objects={
            "Query": {
                "plans": {
                    "crawler": lambda _parent, field_args: load_one(
                        field_args.get_raw("id"),
                        batch_get_crawler_by_id,
                    ),
                },
            },
        },
    )
    result = await grafast(
        schema=schema,
        source="{ crawler(id: 102) { id name } }",
    )
    assert result.errors is None
    assert result.data == {"crawler": {"id": 102, "name": "Princess Donut"}}
