"""Tracer 3 RED: Polymorphism (__typename resolution via interfaces)."""

import pytest

from pygrafast import grafast, make_grafast_schema
from pygrafast.steps import lambda_
from pygrafast.steps.load_one import load_one


CRAWLERS = [
    {"id": 101, "species": "Human", "name": "Carl", "deleted": False},
    {"id": 102, "species": "Cat", "name": "Princess Donut", "deleted": False},
    {"id": 107, "species": "Human", "name": "Hekla", "deleted": True},
]


def batch_get_crawler_by_id(ids, _extra):
    return [next((c for c in CRAWLERS if c["id"] == id), None) for id in ids]


def crawler_to_type_name(crawler):
    if crawler is None:
        return None
    if crawler.get("deleted"):
        return "DeletedCrawler"
    return "ActiveCrawler"


@pytest.mark.asyncio
async def test_crawler_polymorphic_active():
    """crawler(id:101) returns ActiveCrawler with species."""
    schema = make_grafast_schema(
        type_defs="""
            interface Crawler {
                id: Int!
                name: String!
            }
            type ActiveCrawler implements Crawler {
                id: Int!
                name: String!
                species: String
            }
            type DeletedCrawler implements Crawler {
                id: Int!
                name: String!
            }
            type Query {
                crawler(id: Int!): Crawler
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
        interfaces={
            "Crawler": {
                "planType": lambda crawler_step: {
                    "$__typename": lambda_(crawler_step, crawler_to_type_name),
                },
            },
        },
    )
    result = await grafast(
        schema=schema,
        source="""
        {
            crawler(id: 101) {
                __typename
                id
                name
                ... on ActiveCrawler {
                    species
                }
            }
        }
        """,
    )
    assert result.errors is None
    assert result.data == {
        "crawler": {
            "__typename": "ActiveCrawler",
            "id": 101,
            "name": "Carl",
            "species": "Human",
        }
    }


@pytest.mark.asyncio
async def test_crawler_polymorphic_deleted():
    """crawler(id:107) returns DeletedCrawler."""
    schema = make_grafast_schema(
        type_defs="""
            interface Crawler {
                id: Int!
                name: String!
            }
            type ActiveCrawler implements Crawler {
                id: Int!
                name: String!
                species: String
            }
            type DeletedCrawler implements Crawler {
                id: Int!
                name: String!
            }
            type Query {
                crawler(id: Int!): Crawler
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
        interfaces={
            "Crawler": {
                "planType": lambda crawler_step: {
                    "$__typename": lambda_(crawler_step, crawler_to_type_name),
                },
            },
        },
    )
    result = await grafast(
        schema=schema,
        source="""
        {
            crawler(id: 107) {
                __typename
                id
                name
                ... on ActiveCrawler {
                    species
                }
            }
        }
        """,
    )
    assert result.errors is None
    assert result.data == {
        "crawler": {
            "__typename": "DeletedCrawler",
            "id": 107,
            "name": "Hekla",
        }
    }


@pytest.mark.asyncio
async def test_crawler_not_found_polymorphic():
    """crawler(id:999) returns null."""
    schema = make_grafast_schema(
        type_defs="""
            interface Crawler {
                id: Int!
                name: String!
            }
            type ActiveCrawler implements Crawler {
                id: Int!
                name: String!
                species: String
            }
            type DeletedCrawler implements Crawler {
                id: Int!
                name: String!
            }
            type Query {
                crawler(id: Int!): Crawler
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
        interfaces={
            "Crawler": {
                "planType": lambda crawler_step: {
                    "$__typename": lambda_(crawler_step, crawler_to_type_name),
                },
            },
        },
    )
    result = await grafast(
        schema=schema,
        source="{ crawler(id: 999) { __typename id name } }",
    )
    assert result.errors is None
    assert result.data == {"crawler": None}
