"""DCC test schema - Python port of dcc-schema.ts.

Defines a GraphQL schema with plan resolvers for the Dungeon Crawler Carl
test data, used for integration testing.
"""

from __future__ import annotations

from typing import Any

from pygrafast import make_grafast_schema
from pygrafast.steps import lambda_
from pygrafast.steps.access import access
from pygrafast.steps.constant import constant
from pygrafast.steps.context_step import context
from pygrafast.steps.each import each
from pygrafast.steps.get import get
from pygrafast.steps.load_many import load_many
from pygrafast.steps.load_one import load_one

from .dcc_data import (
    batch_get_club_by_id,
    batch_get_consumable_by_id,
    batch_get_crawler_by_id,
    batch_get_equipment_by_id,
    batch_get_friend_ids_by_crawler_id,
    batch_get_locations_by_floor_number,
    batch_get_loot_box_by_id,
    batch_get_loot_data_by_item_type_and_id,
    batch_get_loot_data_by_loot_box_id,
    batch_get_misc_item_by_id,
    batch_get_npc_by_id,
    batch_get_safe_room_by_id,
    batch_get_stairwell_by_id,
    batch_get_utility_item_by_id,
    make_db,
)

# Type definitions (the full DCC schema)
TYPE_DEFS = """
    # For the tests
    directive @incremental on QUERY | MUTATION | SUBSCRIPTION
    scalar _RawJSON
    directive @variables(values: _RawJSON!) on QUERY | MUTATION | SUBSCRIPTION
    directive @expectError on QUERY | MUTATION | SUBSCRIPTION

    enum Species {
        HUMAN
        CAT
        CROCODILIAN
        CHANGELING
        ROCK_MONSTER
        HALF_ELF
        GONDII
        BOPCA
    }

    interface HasInventory {
        items(first: Int): [Item]
    }

    type Guide implements NPC & Character {
        id: Int!
        name: String!
        species: Species
        exCrawler: Boolean
        friends(first: Int): [Character]
        bestFriend: Character
    }
    type Manager implements NPC & Character & HasInventory {
        id: Int!
        name: String!
        species: Species
        items(first: Int): [Item]
        exCrawler: Boolean
        friends(first: Int): [Character]
        bestFriend: Character
        client: ActiveCrawler
    }
    type Security implements NPC & Character {
        id: Int!
        name: String!
        species: Species
        exCrawler: Boolean
        friends(first: Int): [Character]
        bestFriend: Character
        clients: [ActiveCrawler!]
    }
    type Staff implements NPC & Character & HasInventory {
        id: Int!
        name: String!
        species: Species
        exCrawler: Boolean
        bestFriend: Character
        friends(first: Int): [Character]
        items(first: Int): [Item]
    }

    interface NPC implements Character {
        id: Int!
        name: String!
        species: Species
        exCrawler: Boolean
        bestFriend: Character
        friends(first: Int): [Character]
    }
    interface Character {
        id: Int!
        name: String!
    }
    interface Crawler implements Character {
        id: Int!
        name: String!
        crawlerNumber: Int
    }
    type DeletedCrawler implements Crawler & Character {
        id: Int!
        name: String!
        crawlerNumber: Int
    }
    type ActiveCrawler implements Crawler & Character & HasInventory {
        id: Int!
        name: String!
        species: Species
        items(first: Int): [Item]
        favouriteItem: Item
        friends(first: Int): [Character]
        bestFriend: ActiveCrawler
        crawlerNumber: Int
    }

    interface Item {
        id: Int!
        name: String
        canBeFoundIn: [LootBox]
    }
    interface HasContents {
        contents(first: Int): [Item]
    }
    interface Created {
        creator: Crawler
    }
    type Equipment implements Item & Created & HasContents {
        id: Int!
        name: String
        canBeFoundIn: [LootBox]
        contents(first: Int): [Item]
        creator: Crawler
        currentDurability: Int
        maxDurability: Int
    }
    type Consumable implements Item & Created & HasContents {
        id: Int!
        name: String
        canBeFoundIn: [LootBox]
        contents(first: Int): [Item]
        creator: Crawler
        effect: String
    }
    type MiscItem implements Item {
        id: Int!
        name: String
        canBeFoundIn: [LootBox]
    }
    type UtilityItem implements Item {
        id: Int!
        name: String
        canBeFoundIn: [LootBox]
    }

    type LootBox {
        id: Int!
        tier: String
        category: String
        possibleItems: [Item]
    }

    interface Location {
        id: Int!
        name: String!
        floors: [Floor!]!
    }

    union SafeRoomStock = Consumable | MiscItem | Equipment
    union ClubStock = Consumable | MiscItem | UtilityItem

    type SafeRoom implements Location {
        id: Int!
        name: String!
        floors: [Floor!]!
        hasPersonalSpace: Boolean
        manager: NPC
        stock: [SafeRoomStock]
    }

    type Club implements Location {
        id: Int!
        name: String!
        floors: [Floor!]!
        manager: NPC
        security: [Security!]
        tagline: String!
        stock: [ClubStock]
    }

    type Stairwell implements Location {
        id: Int!
        name: String!
        floors: [Floor!]!
    }

    type BetaLocation implements Location {
        id: Int!
        name: String!
        floors: [Floor!]!
    }

    type Floor {
        number: Int!
        locations: [Location]
    }

    enum ItemType {
        Equipment
        Consumable
        UtilityItem
        MiscItem
    }

    type Query {
        crawler(id: Int!): Crawler
        character(id: Int!): Character
        npc(id: Int!): NPC
        floor(number: Int!): Floor
        item(type: ItemType!, id: Int!): Item
        brokenItem: Item
    }
"""


def _apply_limit(args: list[Any]) -> Any:
    """Apply a limit to a list, like TS applyLimit."""
    lst, count = args
    if lst is None:
        return lst
    if count is not None:
        return list(lst)[:count]
    return lst


def _crawler_to_type_name(crawler: Any) -> str | None:
    if crawler is None:
        return None
    if isinstance(crawler, dict) and crawler.get("deleted"):
        return "DeletedCrawler"
    return "ActiveCrawler"


def _npc_to_type_name(npc: Any) -> str | None:
    if not npc:
        return None
    if isinstance(npc, dict):
        npc_type = npc.get("type")
        if npc_type in ("Manager", "Security", "Guide", "Staff"):
            return npc_type
    return None


def _extract_crawler_id(id_val: int) -> int | None:
    if 100 < id_val < 200:
        return id_val
    return None


def _extract_npc_id(id_val: int) -> int | None:
    if 300 < id_val < 400:
        return id_val
    return None


def _decode_item_spec(item_spec: str) -> dict[str, Any]:
    typename, raw_id = item_spec.split(":")
    return {"__typename": typename, "id": int(raw_id)}


def _encode_item_spec(args: list[Any]) -> str:
    type_name, id_val = args
    return f"{type_name}:{id_val}"


def _get_floor(number: int) -> dict[str, int] | None:
    if 1 <= number <= 18:
        return {"number": number}
    return None


def _coalesce_values(values: list[Any]) -> Any:
    """Return first non-None value."""
    for v in values:
        if v is not None:
            return v
    return None


def make_base_args() -> dict[str, Any]:
    """Create the DCC schema and context, equivalent to TS makeBaseArgs()."""
    dcc_db = make_db()

    schema = make_grafast_schema(
        type_defs=TYPE_DEFS,
        objects={
            "Query": {
                "plans": {
                    "crawler": lambda _parent, field_args: load_one(
                        field_args.get_raw("id"),
                        {"load": batch_get_crawler_by_id, "shared": context().get("dccDb")},
                    ),
                    "character": _plan_query_character,
                    "floor": lambda _parent, field_args: lambda_(
                        field_args.get_raw("number"),
                        _get_floor,
                    ),
                    "npc": lambda _parent, field_args: load_one(
                        field_args.get_raw("id"),
                        {"load": batch_get_npc_by_id, "shared": context().get("dccDb")},
                    ),
                    "brokenItem": lambda _parent, _field_args: constant("Utility:999"),
                    "item": lambda _parent, field_args: lambda_(
                        [field_args.get_raw("type"), field_args.get_raw("id")],
                        lambda args: f"{args[0]}:{args[1]}",
                    ),
                },
            },
            "ActiveCrawler": {
                "plans": {
                    "bestFriend": lambda crawler_step, _fa: load_one(
                        get(crawler_step, "bestFriend"),
                        {"load": batch_get_crawler_by_id, "shared": context().get("dccDb")},
                    ),
                    "friends": _plan_active_crawler_friends,
                    "items": lambda crawler_step, field_args: lambda_(
                        [get(crawler_step, "items"), field_args.get_raw("first")],
                        _apply_limit,
                    ),
                    "favouriteItem": lambda crawler_step, _fa: get(crawler_step, "favouriteItem"),
                },
            },
            "Manager": {
                "plans": {
                    "friends": _plan_npc_friends,
                    "bestFriend": lambda npc_step, _fa: get(npc_step, "bestFriend"),
                    "client": lambda manager_step, _fa: load_one(
                        get(manager_step, "client"),
                        {"load": batch_get_crawler_by_id, "shared": context().get("dccDb")},
                    ),
                    "items": lambda npc_step, field_args: lambda_(
                        [get(npc_step, "items"), field_args.get_raw("first")],
                        _apply_limit,
                    ),
                },
            },
            "Security": {
                "plans": {
                    "friends": _plan_npc_friends,
                    "bestFriend": lambda npc_step, _fa: get(npc_step, "bestFriend"),
                    "clients": lambda security_step, _fa: each(
                        get(security_step, "clients"),
                        lambda id_step: load_one(
                            id_step,
                            {"load": batch_get_crawler_by_id, "shared": context().get("dccDb")},
                        ),
                    ),
                },
            },
            "Guide": {
                "plans": {
                    "friends": _plan_npc_friends,
                    "bestFriend": lambda npc_step, _fa: get(npc_step, "bestFriend"),
                },
            },
            "Staff": {
                "plans": {
                    "friends": _plan_npc_friends,
                    "bestFriend": lambda npc_step, _fa: get(npc_step, "bestFriend"),
                    "items": lambda npc_step, field_args: lambda_(
                        [get(npc_step, "items"), field_args.get_raw("first")],
                        _apply_limit,
                    ),
                },
            },
            "Floor": {
                "plans": {
                    "locations": lambda floor_step, _fa: load_many(
                        get(floor_step, "number"),
                        {"load": batch_get_locations_by_floor_number, "shared": context().get("dccDb")},
                    ),
                },
            },
            "Equipment": {
                "plans": {
                    "creator": lambda source_step, _fa: load_one(
                        get(source_step, "creator"),
                        {"load": batch_get_crawler_by_id, "shared": context().get("dccDb")},
                    ),
                },
            },
            "Consumable": {
                "plans": {
                    "creator": lambda source_step, _fa: load_one(
                        get(source_step, "creator"),
                        {"load": batch_get_crawler_by_id, "shared": context().get("dccDb")},
                    ),
                },
            },
        },
        interfaces={
            "Crawler": {
                "planType": lambda crawler_step: {
                    "$__typename": lambda_(crawler_step, _crawler_to_type_name),
                },
            },
            "Character": {
                "planType": lambda specifier_step: _plan_character_type(specifier_step),
            },
            "NPC": {
                "planType": lambda npc_id_step: _plan_npc_type(npc_id_step),
                "plans": {
                    "friends": _plan_npc_friends,
                    "bestFriend": lambda npc_step, _fa: get(npc_step, "bestFriend"),
                },
            },
            "Item": {
                "planType": lambda item_spec_step: _plan_item_type(item_spec_step),
            },
            "Location": {
                "planType": lambda location_step: _plan_location_type(location_step),
            },
        },
        unions={
            "SafeRoomStock": {
                "planType": lambda item_spec_step: _plan_item_type(item_spec_step),
            },
            "ClubStock": {
                "planType": lambda item_spec_step: _plan_item_type(item_spec_step),
            },
        },
        enums={
            "Species": {
                "values": {
                    "HUMAN": {"value": "Human"},
                    "CAT": {"value": "Cat"},
                    "CROCODILIAN": {"value": "Crocodilian"},
                    "CHANGELING": {"value": "Changeling"},
                    "ROCK_MONSTER": {"value": "Rock Monster"},
                    "HALF_ELF": {"value": "Half Elf"},
                    "GONDII": {"value": "Gondii"},
                    "BOPCA": {"value": "Bopca Protector"},
                },
            },
        },
    )

    return {
        "schema": schema,
        "context_value": {"dccDb": dcc_db},
        "variable_values": {},
    }


def _plan_query_character(_parent: Any, field_args: Any) -> Any:
    """Plan Query.character - resolves a character by ID.

    Loads either a crawler (100-199) or NPC (300-399) depending on the ID.
    """
    id_step = field_args.get_raw("id")
    db_step = context().get("dccDb")

    crawler_id_step = lambda_(id_step, _extract_crawler_id)
    crawler_step = load_one(
        crawler_id_step,
        {"load": batch_get_crawler_by_id, "shared": db_step},
    )

    npc_id_step = lambda_(id_step, _extract_npc_id)
    npc_step = load_one(
        npc_id_step,
        {"load": batch_get_npc_by_id, "shared": db_step},
    )

    # Return whichever loaded successfully
    return lambda_([crawler_step, npc_step], _coalesce_values)


def _plan_npc_friends(npc_step: Any, field_args: Any) -> Any:
    """Plan NPC friends - resolves friend IDs to Character objects with limit."""
    friends_list = get(npc_step, "friends")
    first = field_args.get_raw("first")
    limited = lambda_([friends_list, first], _apply_limit)

    def resolve_friend(friend_id_step: Any) -> Any:
        db = context().get("dccDb")
        crawler_id = lambda_(friend_id_step, _extract_crawler_id)
        crawler = load_one(
            crawler_id,
            {"load": batch_get_crawler_by_id, "shared": db},
        )
        npc_id = lambda_(friend_id_step, _extract_npc_id)
        npc = load_one(
            npc_id,
            {"load": batch_get_npc_by_id, "shared": db},
        )
        return lambda_([crawler, npc], _coalesce_values)

    return each(limited, resolve_friend)


def _plan_active_crawler_friends(crawler_step: Any, field_args: Any) -> Any:
    """Plan ActiveCrawler.friends - returns [Character] via friend IDs.

    In the TS version, the friends field returns raw IDs and the bucket system
    resolves them through Character.planType. In Python, we resolve explicitly
    via each().
    """
    crawler_id = get(crawler_step, "id")
    db_step = context().get("dccDb")
    friend_ids = load_many(
        crawler_id,
        {"load": batch_get_friend_ids_by_crawler_id, "shared": db_step},
    )

    # Resolve each friend ID through Character loading.
    # Each friend can be a crawler (100-199) or NPC (300-399).
    def resolve_friend(friend_id_step: Any) -> Any:
        """Resolve a single friend ID to a Character object."""
        db = context().get("dccDb")

        crawler_id = lambda_(friend_id_step, _extract_crawler_id)
        crawler = load_one(
            crawler_id,
            {"load": batch_get_crawler_by_id, "shared": db},
        )

        npc_id = lambda_(friend_id_step, _extract_npc_id)
        npc = load_one(
            npc_id,
            {"load": batch_get_npc_by_id, "shared": db},
        )

        return lambda_([crawler, npc], _coalesce_values)

    return each(friend_ids, resolve_friend)


def _character_to_type_name(obj: Any) -> str | None:
    """Determine __typename from a loaded character object."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        # Check if it's an NPC first (NPCs have a "type" field, crawlers don't)
        if "type" in obj:
            return _npc_to_type_name(obj)
        # Check if it's a crawler
        if obj.get("deleted"):
            return "DeletedCrawler"
        # Active crawler (has an id in the crawler range, or has species without type)
        if "id" in obj:
            return "ActiveCrawler"
    return None


def _plan_character_type(character_step: Any) -> dict[str, Any]:
    """Plan Character interface resolution.

    In our simplified version, character_step is already a loaded object
    (either a crawler dict or NPC dict). We just need to determine __typename.
    """
    typename_step = lambda_(character_step, _character_to_type_name)
    return {"$__typename": typename_step}


def _plan_npc_type(npc_step: Any) -> dict[str, Any]:
    """Plan NPC interface resolution.

    In the simplified Python version, npc_step is already a loaded NPC object
    (not just an ID) since Query.npc does the loadOne.
    """
    typename_step = lambda_(npc_step, _npc_to_type_name)
    return {"$__typename": typename_step}


def _plan_item_type(item_spec_step: Any) -> dict[str, Any]:
    """Plan Item interface/union resolution."""
    decoded_step = lambda_(item_spec_step, _decode_item_spec)
    typename_step = get(decoded_step, "__typename")
    return {"$__typename": typename_step}


def _plan_location_type(location_step: Any) -> dict[str, Any]:
    """Plan Location interface resolution."""
    typename_step = get(location_step, "type")
    return {"$__typename": typename_step}
