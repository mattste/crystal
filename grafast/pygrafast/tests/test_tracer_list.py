"""Tracer 4 RED: Lists + each() + LoadMany + DCC fixture."""

import pytest

from pygrafast import grafast, make_grafast_schema
from pygrafast.steps import lambda_
from pygrafast.steps.access import access
from pygrafast.steps.load_one import load_one
from pygrafast.steps.load_many import load_many
from pygrafast.steps.each import each
from pygrafast.steps.get import get


CRAWLERS = [
    {
        "id": 101,
        "species": "Human",
        "name": "Carl",
        "friendIds": [102, 103],
    },
    {
        "id": 102,
        "species": "Cat",
        "name": "Princess Donut",
        "friendIds": [101, 103],
    },
    {
        "id": 103,
        "species": "Human",
        "name": "Katia",
        "friendIds": [101, 102],
    },
]


def batch_get_crawler_by_id(ids, _extra):
    return [next((c for c in CRAWLERS if c["id"] == id), None) for id in ids]


def batch_get_friend_ids(ids, _extra):
    """LoadMany: for each crawler id, return list of friend ids."""
    results = []
    for id in ids:
        crawler = next((c for c in CRAWLERS if c["id"] == id), None)
        results.append(crawler.get("friendIds", []) if crawler else None)
    return results


@pytest.mark.asyncio
async def test_list_field():
    """Query with a list field returning scalar items."""
    schema = make_grafast_schema(
        type_defs="""
            type Query {
                crawler(id: Int!): Crawler
            }
            type Crawler {
                id: Int!
                name: String!
                friendIds: [Int]
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
        source="{ crawler(id: 101) { id name friendIds } }",
    )
    assert result.errors is None
    assert result.data == {
        "crawler": {"id": 101, "name": "Carl", "friendIds": [102, 103]}
    }


@pytest.mark.asyncio
async def test_list_of_objects_with_each():
    """Query with a list of objects using each() to resolve each item."""
    schema = make_grafast_schema(
        type_defs="""
            type Query {
                crawler(id: Int!): Crawler
            }
            type Crawler {
                id: Int!
                name: String!
                friends: [Crawler]
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
            "Crawler": {
                "plans": {
                    "friends": lambda crawler_step, _field_args: each(
                        load_many(
                            get(crawler_step, "id"),
                            batch_get_friend_ids,
                        ),
                        lambda friend_id_step: load_one(
                            friend_id_step,
                            batch_get_crawler_by_id,
                        ),
                    ),
                },
            },
        },
    )
    result = await grafast(
        schema=schema,
        source="{ crawler(id: 101) { id name friends { id name } } }",
    )
    assert result.errors is None
    assert result.data == {
        "crawler": {
            "id": 101,
            "name": "Carl",
            "friends": [
                {"id": 102, "name": "Princess Donut"},
                {"id": 103, "name": "Katia"},
            ],
        }
    }
