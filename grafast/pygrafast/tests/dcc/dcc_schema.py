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
from pygrafast.steps.list_step import list_
from pygrafast.steps.load_many import load_many
from pygrafast.steps.connection import connection
from pygrafast.steps.load_one import load_one

from .dcc_data import (
    batch_get_beta_location_by_id,
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
        itemsConnection(
          first: Int
          after: String
          offset: Int
          last: Int
          before: String
        ): ItemConnection
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
        itemsConnection(
          first: Int
          after: String
          offset: Int
          last: Int
          before: String
        ): ItemConnection
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
        itemsConnection(
          first: Int
          after: String
          offset: Int
          last: Int
          before: String
        ): ItemConnection
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
        itemsConnection(
          first: Int
          after: String
          offset: Int
          last: Int
          before: String
        ): ItemConnection
        favouriteItem: Item
        friends(first: Int): [Character]
        friendsConnection(
          first: Int
          after: String
          offset: Int
          last: Int
          before: String
        ): CharacterConnection
        bestFriend: ActiveCrawler
        crawlerNumber: Int
    }

    type ItemConnection {
        edges: [ItemEdge]
        nodes: [Item]
        pageInfo: PageInfo!
    }
    type ItemEdge {
        node: Item
        cursor: String!
    }
    type CharacterConnection {
        edges: [CharacterEdge]
        nodes: [Character]
        pageInfo: PageInfo!
    }
    type CharacterEdge {
        node: Character
        cursor: String!
    }
    type PageInfo {
        hasNextPage: Boolean!
        hasPreviousPage: Boolean!
        startCursor: String
        endCursor: String
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


def _decode_item_spec(item_spec: str | None) -> dict[str, Any] | None:
    if item_spec is None:
        return None
    typename, raw_id = item_spec.split(":")
    return {"__typename": typename, "id": int(raw_id)}


def _encode_item_spec(args: list[Any]) -> str:
    type_name, id_val = args
    return f"{type_name}:{id_val}"


def _load_item_by_decoded(args: list[Any]) -> dict[str, Any] | None:
    """Given [decoded_spec, equipment, consumable, utility_item, misc_item],
    select the correct loaded item based on __typename and add __typename to it."""
    decoded, equipment, consumable, utility_item, misc_item = args
    if decoded is None:
        return None
    typename = decoded.get("__typename")
    data = None
    if typename == "Equipment":
        data = equipment
    elif typename == "Consumable":
        data = consumable
    elif typename == "UtilityItem":
        data = utility_item
    elif typename == "MiscItem":
        data = misc_item
    if data is None:
        return None
    # Return a copy with __typename added
    result = dict(data)
    result["__typename"] = typename
    return result


def _get_floor(number: int) -> dict[str, int] | None:
    if 1 <= number <= 18:
        return {"number": number}
    return None


def _merge_location_data(args: list[Any]) -> Any:
    """Merge type-specific data with shared location data (delegate pattern).

    The type-specific object (e.g. SafeRoom, Club) gets type/name/floors/id
    from the location object.
    """
    location, type_specific = args
    if type_specific is None:
        return None
    merged = dict(type_specific)
    if location:
        for key in ("type", "name", "floors", "id"):
            if key in location:
                merged[key] = location[key]
    return merged


def _coalesce_values(values: list[Any]) -> Any:
    """Return first non-None value."""
    for v in values:
        if v is not None:
            return v
    return None


def _loot_boxes_for_item(type_step: Any, id_step: Any) -> Any:
    """Given item type and id steps, load the loot boxes that can contain this item."""
    db = context().get("dccDb")
    key_step = list_([type_step, id_step])
    loot_data = load_many(
        key_step,
        {"load": batch_get_loot_data_by_item_type_and_id, "shared": db},
    )
    return each(loot_data, lambda loot_datum_step: load_one(
        get(loot_datum_step, "lootBoxId"),
        {"load": batch_get_loot_box_by_id, "shared": context().get("dccDb")},
    ))


def _plan_loot_box_possible_items(loot_box_step: Any, _fa: Any) -> Any:
    """Load the possible items for a loot box."""
    db = context().get("dccDb")
    loot_data = load_many(
        get(loot_box_step, "id"),
        {"load": batch_get_loot_data_by_loot_box_id, "shared": db},
    )
    return each(loot_data, lambda loot_datum_step: _resolve_item_spec_step(
        lambda_(
            [get(loot_datum_step, "itemType"), get(loot_datum_step, "itemId")],
            _encode_item_spec,
        ),
    ))


def _resolve_item_spec_step(item_spec_step: Any) -> Any:
    """Given a step producing an item spec string (e.g. "Equipment:201"),
    return a step producing a loaded item dict with __typename.

    This performs:
      1. Decode the spec to get {__typename, id}
      2. Load from all four item tables using the id
      3. Select the correct one based on __typename
    """
    db = context().get("dccDb")
    decoded = lambda_(item_spec_step, _decode_item_spec)
    id_step = get(decoded, "id")

    equipment = load_one(id_step, {"load": batch_get_equipment_by_id, "shared": db})
    consumable = load_one(id_step, {"load": batch_get_consumable_by_id, "shared": db})
    utility_item = load_one(id_step, {"load": batch_get_utility_item_by_id, "shared": db})
    misc_item = load_one(id_step, {"load": batch_get_misc_item_by_id, "shared": db})

    return lambda_(
        [decoded, equipment, consumable, utility_item, misc_item],
        _load_item_by_decoded,
    )


def _resolve_item_spec_list_step(spec_list_step: Any, first_step: Any = None) -> Any:
    """Resolve a list of item spec strings, with optional limit."""
    if first_step is not None:
        limited = lambda_([spec_list_step, first_step], _apply_limit)
    else:
        limited = spec_list_step
    return each(limited, _resolve_item_spec_step)


def _plan_active_crawler_friends_connection(crawler_step: Any, field_args: Any) -> Any:
    """Plan ActiveCrawler.friendsConnection - paginated friends list."""
    crawler_id = get(crawler_step, "id")
    db_step = context().get("dccDb")
    friend_ids = load_many(
        crawler_id,
        {"load": batch_get_friend_ids_by_crawler_id, "shared": db_step},
    )

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

    return connection(friend_ids, field_args, node_callback=resolve_friend)


def _plan_items_connection(source_step: Any, field_args: Any) -> Any:
    """Plan itemsConnection - paginated items list for HasInventory types."""
    items_step = get(source_step, "items")
    return connection(items_step, field_args, node_callback=_resolve_item_spec_step)


def _plan_location_floors(place_step: Any, _fa: Any) -> Any:
    """Plan Location.floors - maps floor numbers to Floor objects.

    Corresponds to TS SharedLocationResolvers.floors.
    """
    floors_step = get(place_step, "floors")
    return each(floors_step, lambda floor_num_step: lambda_(floor_num_step, _get_floor))


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
                    "brokenItem": lambda _parent, _field_args: _resolve_item_spec_step(
                        constant("Utility:999"),
                    ),
                    "item": lambda _parent, field_args: _resolve_item_spec_step(
                        lambda_(
                            [field_args.get_raw("type"), field_args.get_raw("id")],
                            lambda args: f"{args[0]}:{args[1]}",
                        ),
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
                    "friendsConnection": _plan_active_crawler_friends_connection,
                    "items": lambda crawler_step, field_args: _resolve_item_spec_list_step(
                        get(crawler_step, "items"),
                        field_args.get_raw("first"),
                    ),
                    "itemsConnection": _plan_items_connection,
                    "favouriteItem": lambda crawler_step, _fa: _resolve_item_spec_step(
                        get(crawler_step, "favouriteItem"),
                    ),
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
                    "items": lambda npc_step, field_args: _resolve_item_spec_list_step(
                        get(npc_step, "items"),
                        field_args.get_raw("first"),
                    ),
                    "itemsConnection": _plan_items_connection,
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
                    "items": lambda npc_step, field_args: _resolve_item_spec_list_step(
                        get(npc_step, "items"),
                        field_args.get_raw("first"),
                    ),
                    "itemsConnection": _plan_items_connection,
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
            "SafeRoom": {
                "plans": {
                    "floors": _plan_location_floors,
                    "manager": lambda sr_step, _fa: load_one(
                        get(sr_step, "manager"),
                        {"load": batch_get_npc_by_id, "shared": context().get("dccDb")},
                    ),
                    "stock": lambda sr_step, _fa: _resolve_item_spec_list_step(
                        get(sr_step, "stock"),
                    ),
                },
            },
            "Club": {
                "plans": {
                    "floors": _plan_location_floors,
                    "manager": lambda club_step, _fa: load_one(
                        get(club_step, "manager"),
                        {"load": batch_get_npc_by_id, "shared": context().get("dccDb")},
                    ),
                    "security": lambda club_step, _fa: each(
                        get(club_step, "security"),
                        lambda id_step: load_one(
                            id_step,
                            {"load": batch_get_npc_by_id, "shared": context().get("dccDb")},
                        ),
                    ),
                    "stock": lambda club_step, _fa: _resolve_item_spec_list_step(
                        get(club_step, "stock"),
                    ),
                },
            },
            "Stairwell": {
                "plans": {
                    "floors": _plan_location_floors,
                },
            },
            "BetaLocation": {
                "plans": {
                    "floors": _plan_location_floors,
                },
            },
            "Equipment": {
                "plans": {
                    "creator": lambda source_step, _fa: load_one(
                        get(source_step, "creator"),
                        {"load": batch_get_crawler_by_id, "shared": context().get("dccDb")},
                    ),
                    "canBeFoundIn": lambda source_step, _fa: _loot_boxes_for_item(
                        constant("Equipment"), get(source_step, "id"),
                    ),
                    "contents": lambda source_step, field_args: _resolve_item_spec_list_step(
                        get(source_step, "contents"),
                        field_args.get_raw("first"),
                    ),
                },
            },
            "Consumable": {
                "plans": {
                    "creator": lambda source_step, _fa: load_one(
                        get(source_step, "creator"),
                        {"load": batch_get_crawler_by_id, "shared": context().get("dccDb")},
                    ),
                    "canBeFoundIn": lambda source_step, _fa: _loot_boxes_for_item(
                        constant("Consumable"), get(source_step, "id"),
                    ),
                    "contents": lambda source_step, field_args: _resolve_item_spec_list_step(
                        get(source_step, "contents"),
                        field_args.get_raw("first"),
                    ),
                },
            },
            "UtilityItem": {
                "plans": {
                    "canBeFoundIn": lambda source_step, _fa: _loot_boxes_for_item(
                        constant("UtilityItem"), get(source_step, "id"),
                    ),
                },
            },
            "MiscItem": {
                "plans": {
                    "canBeFoundIn": lambda source_step, _fa: _loot_boxes_for_item(
                        constant("MiscItem"), get(source_step, "id"),
                    ),
                },
            },
            "LootBox": {
                "plans": {
                    "possibleItems": _plan_loot_box_possible_items,
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
                "planType": lambda item_step: _plan_item_type(item_step),
                "plans": {
                    "canBeFoundIn": lambda source_step, _fa: _loot_boxes_for_item(
                        get(source_step, "__typename"), get(source_step, "id"),
                    ),
                },
            },
            "HasContents": {
                "plans": {
                    "contents": lambda source_step, field_args: _resolve_item_spec_list_step(
                        get(source_step, "contents"),
                        field_args.get_raw("first"),
                    ),
                },
            },
            "Created": {
                "plans": {
                    "creator": lambda source_step, _fa: load_one(
                        get(source_step, "creator"),
                        {"load": batch_get_crawler_by_id, "shared": context().get("dccDb")},
                    ),
                },
            },
            "HasInventory": {
                "plans": {
                    "items": lambda source_step, field_args: _resolve_item_spec_list_step(
                        get(source_step, "items"),
                        field_args.get_raw("first"),
                    ),
                    "itemsConnection": _plan_items_connection,
                },
            },
            "Location": {
                "planType": lambda location_step: _plan_location_type(location_step),
                "plans": {
                    "floors": _plan_location_floors,
                },
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


def _plan_item_type(item_step: Any) -> dict[str, Any]:
    """Plan Item interface/union resolution.

    item_step now produces a loaded item dict with __typename,
    so we just read __typename from it.
    """
    typename_step = get(item_step, "__typename")
    return {"$__typename": typename_step}


def _plan_location_type(location_step: Any) -> dict[str, Any]:
    """Plan Location interface resolution.

    Returns $__typename and planForType which loads type-specific data
    (SafeRoom, Club, Stairwell) and merges it with the shared location fields.
    """
    db = context().get("dccDb")
    typename_step = get(location_step, "type")
    id_step = get(location_step, "id")

    def plan_for_type(t: Any) -> Any:
        if t.name == "SafeRoom":
            saferoom = load_one(
                id_step,
                {"load": batch_get_safe_room_by_id, "shared": db},
            )
            return lambda_([location_step, saferoom], _merge_location_data)
        if t.name == "Club":
            club = load_one(
                id_step,
                {"load": batch_get_club_by_id, "shared": db},
            )
            return lambda_([location_step, club], _merge_location_data)
        if t.name == "Stairwell":
            stairwell = load_one(
                id_step,
                {"load": batch_get_stairwell_by_id, "shared": db},
            )
            return lambda_([location_step, stairwell], _merge_location_data)
        if t.name == "BetaLocation":
            # Explicitly return None — BetaLocation data is intentionally null
            return None
        return None

    return {"$__typename": typename_step, "planForType": plan_for_type}
