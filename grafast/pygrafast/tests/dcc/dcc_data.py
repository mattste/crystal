from __future__ import annotations

from typing import Literal, TypedDict


# --- Type aliases ---

ItemType = Literal["Equipment", "Consumable", "UtilityItem", "MiscItem"]
ItemSpec = str  # e.g. "Equipment:201"
LocationType = Literal["BetaLocation", "SafeRoom", "Club", "Stairwell"]
LootTier = Literal["Bronze", "Silver", "Gold"]
LootCategory = Literal["Adventurer", "Boss", "Fan", "Quest"]


# --- Data TypedDicts ---


class CrawlerData(TypedDict, total=False):
    id: int  # required, but total=False for optional fields
    species: Literal["Human", "Cat", "Crocodilian"]
    name: str
    items: list[ItemSpec]
    favouriteItem: ItemSpec
    friends: list[int]
    bestFriend: int
    crawlerNumber: int
    deleted: Literal[True]


class NpcData(TypedDict, total=False):
    id: int
    type: Literal["Manager", "Security", "Guide", "Staff"]
    species: Literal[
        "Changeling", "Rock Monster", "Half Elf", "Gondii", "Bopca Protector"
    ]
    name: str
    exCrawler: bool
    client: int
    clients: list[int]
    items: list[ItemSpec]
    friends: list[int]
    bestFriend: int


class ItemData(TypedDict, total=False):
    id: int
    name: str
    creator: int
    contents: list[ItemSpec]
    type: str


class EquipmentData(TypedDict, total=False):
    id: int
    name: str
    creator: int
    currentDurability: int
    maxDurability: int
    contents: list[ItemSpec]


class ConsumableData(TypedDict, total=False):
    id: int
    name: str
    creator: int
    effect: str
    contents: list[ItemSpec]


class UtilityItemData(TypedDict, total=False):
    id: int
    name: str
    creator: int
    contents: list[ItemSpec]


class MiscItemData(TypedDict, total=False):
    id: int
    name: str
    creator: int
    contents: list[ItemSpec]


class LootBoxData(TypedDict):
    id: int
    tier: LootTier
    category: LootCategory


class LootDataData(TypedDict):
    id: int
    itemType: ItemType
    itemId: int
    lootBoxId: int
    percentageChance: int


class LocationData(TypedDict):
    id: int
    name: str
    type: LocationType
    floors: list[int]


class SafeRoomData(TypedDict, total=False):
    id: int
    hasPersonalSpace: Literal[True]
    manager: int
    stock: list[ItemSpec]


class ClubData(TypedDict, total=False):
    id: int
    manager: int
    security: list[int]
    tagline: str
    stock: list[ItemSpec]


class StairwellData(TypedDict):
    id: int


class BetaLocationData(TypedDict):
    id: int


class FloorData(TypedDict):
    number: int


class Database(TypedDict):
    crawlers: list[CrawlerData]
    npcs: list[NpcData]
    equipment: list[EquipmentData]
    consumables: list[ConsumableData]
    utilityItems: list[UtilityItemData]
    miscItems: list[MiscItemData]
    lootBoxes: list[LootBoxData]
    lootData: list[LootDataData]
    locations: list[LocationData]
    saferooms: list[SafeRoomData]
    stairwells: list[StairwellData]
    betaLocations: list[BetaLocationData]
    clubs: list[ClubData]


# --- Database factory ---


def make_db() -> Database:
    return {
        "crawlers": [
            {
                "id": 101,
                "species": "Human",
                "name": "Carl",
                "items": [
                    "Consumable:205",
                    "Equipment:211",
                    "Consumable:206",
                    "UtilityItem:206",
                    "Equipment:201",
                    "Equipment:202",
                    "Equipment:203",
                    "Consumable:201",
                    "UtilityItem:202",
                    "Consumable:203",
                    "Consumable:204",
                ],
                "favouriteItem": "Equipment:211",
                "friends": [102, 103, 104, 105, 301],
                "bestFriend": 102,
                "crawlerNumber": 4122,
            },
            {
                "id": 102,
                "species": "Cat",
                "name": "Princess Donut",
                "items": [
                    "Equipment:204",
                    "Equipment:206",
                    "Consumable:201",
                    "UtilityItem:202",
                    "Consumable:203",
                    "Consumable:204",
                    "Consumable:205",
                ],
                "favouriteItem": "Equipment:205",  # Favourite item is not in inventory
                "friends": [101, 103, 104, 105, 301, 302, 303],
                "bestFriend": 101,
                "crawlerNumber": 4119,
            },
            {
                "id": 103,
                "species": "Human",
                "name": "Katia",
                "items": [
                    "Equipment:207",
                    "Consumable:203",
                    "Consumable:204",
                    "Equipment:210",
                ],
                "favouriteItem": "Equipment:210",  # Favourite item has a creator
                "friends": [101, 102],
                "bestFriend": 107,  # Best friend is deleted
                "crawlerNumber": 9077265,
            },
            {
                "id": 104,
                "species": "Human",
                "name": "Imani",
                "items": [
                    "Equipment:208",
                    "Equipment:209",
                    "Consumable:204",
                    "UtilityItem:202",
                    "Consumable:203",
                ],
                "friends": [101, 102, 105],
            },
            {
                "id": 105,
                "species": "Human",
                "name": "Elle",
                "items": ["UtilityItem:202", "Consumable:203"],
                "friends": [101, 102, 104],
            },
            {
                "id": 106,
                "species": "Crocodilian",
                "name": "Dolores",
                "items": ["Consumable:205"],
            },
            {"id": 107, "species": "Human", "name": "Hekla", "deleted": True},
        ],
        "npcs": [
            {
                "id": 301,
                "type": "Manager",
                "species": "Changeling",
                "name": "Mordecai",
                "exCrawler": True,
                "client": 102,
                "items": ["Consumable:203", "Consumable:203", "Consumable:203"],
                "friends": [101, 102, 103, 306],
            },
            {
                "id": 302,
                "type": "Security",
                "species": "Rock Monster",
                "name": "Bomo",
                "friends": [102, 303],
                "clients": [101, 102, 103],
                "bestFriend": 303,
            },
            {
                "id": 303,
                "type": "Security",
                "species": "Rock Monster",
                "name": "Sledge",
                "friends": [102, 302],
                "clients": [101, 102, 103],
                "bestFriend": 302,
            },
            {
                "id": 304,
                "type": "Manager",
                "species": "Half Elf",
                "name": "Tiatha",
                "exCrawler": True,
                "client": 105,
            },
            {
                "id": 305,
                "type": "Staff",
                "species": "Gondii",
                "name": "Orren",
            },
            {
                # Has an item of Equipment type, which isn't allowed in SaferoomStock type
                "id": 306,
                "type": "Staff",
                "species": "Bopca Protector",
                "name": "Tally",
                "friends": [102, 301],
                "items": ["UtilityItem:202", "Equipment:208"],
            },
            {
                "id": 307,
                "type": "Security",
                "species": "Rock Monster",
                "name": "Clay-ton",
                "clients": [105],
            },
        ],
        "equipment": [
            {
                "id": 201,
                "name": "Cloak of Stoutness",
                "currentDurability": 300,
                "maxDurability": 300,
            },
            {
                "id": 202,
                "name": "Toe Ring of the Splatter Skunk",
                "currentDurability": 50,
                "maxDurability": 1000,
            },
            {
                "id": 203,
                "name": "Enchanted War Gauntlet",
                "currentDurability": 50,
                "maxDurability": 1800,
            },
            {"id": 204, "name": "Enchanted Crown", "maxDurability": 5000},
            {
                "id": 205,
                "name": "Enchanted Tiara of Mana",
                "currentDurability": 0,
                "maxDurability": 2500,
            },
            {"id": 206, "name": "Enchanted Anklet", "maxDurability": 100},
            {
                "id": 207,
                "name": "Enchanted Repeating Crossbow",
                "currentDurability": 1500,
                "maxDurability": 3000,
            },
            {
                "id": 208,
                "name": "Longsword",
                "currentDurability": 10000,
                "maxDurability": 10000,
            },
            {
                "id": 209,
                "name": "Enchanted Cloak",
                "currentDurability": 70,
                "maxDurability": 400,
            },
            {
                # This item can have an inventory
                "id": 210,
                "name": "Ugly Backpack With a Completely Useless Design",
                "creator": 101,
                "currentDurability": 100,
                "maxDurability": 100,
                "contents": [
                    "MiscItem:201",
                    "MiscItem:201",
                    "MiscItem:202",
                    "MiscItem:202",
                    "MiscItem:203",
                    "MiscItem:203",
                ],
            },
            {
                "id": 211,
                "name": "Enchanted Anarchist's Battle Rattle",
                "maxDurability": 10000,
                "currentDurability": 10000,
                "contents": ["Equipment:212", "Equipment:213"],
            },
            {"id": 212, "name": "Earth Upgrade Patch", "maxDurability": 10000},
            {"id": 213, "name": "Skyfowl Upgrade Patch", "maxDurability": 10000},
        ],
        "consumables": [
            {
                "id": 201,
                "name": "Rev-Up Immunity Smoothie",
                "effect": "Temporary immunity to all health-seeping conditions and debuffs",
            },
            {
                "id": 203,
                "name": "Mana Potion",
                "effect": "Fully restores MP",
            },
            {
                "id": 204,
                "name": "Healing Potion",
                "effect": "Heal 50%+ total health",
            },
            {
                "id": 205,
                "name": "Dolores Doesn't Splat Potion",
                "creator": 106,
                "effect": "Soften impact surface. Impact x 5",
                "contents": ["Consumable:207", "Consumable:208"],
            },
            {
                "id": 206,
                "name": "Carl's Jug O' Boom",
                "creator": 101,
                "effect": "Intense Fire for (Incendiary Device Handling Skill Level x 15) sec.",
                "contents": ["Consumable:209", "MiscItem:204", "MiscItem:205"],
            },
            {
                "id": 207,
                "name": "Crowd Blast Potion",
                "effect": "Imitates the Crowd Blast skill",
            },
            {
                "id": 208,
                "name": "Rock Buffalo Potion",
                "effect": "A required component of Dolores Doesn't Splat Potion",
            },
            {
                "id": 209,
                "name": "Goblin Oil",
                "effect": "Has many uses",
            },
        ],
        "utilityItems": [
            {"id": 202, "name": "Bandage"},
            {
                "id": 206,
                "name": "Fireball or Custard? Scratchcard",
            },
        ],
        "miscItems": [
            {
                "id": 201,
                "name": "Scrap Metal",
            },
            {
                "id": 202,
                "name": "Scrap Metal Pole",
            },
            {
                "id": 203,
                "name": "Metal Bearing",
            },
            {
                "id": 204,
                "name": "Low-Grade Moonshine Jug",
            },
            {
                "id": 205,
                "name": "Torch",
            },
        ],
        "lootBoxes": [
            {"id": 501, "tier": "Bronze", "category": "Adventurer"},
            {"id": 502, "tier": "Bronze", "category": "Quest"},
            {"id": 503, "tier": "Silver", "category": "Adventurer"},
            {"id": 504, "tier": "Silver", "category": "Boss"},
            {"id": 505, "tier": "Gold", "category": "Fan"},
            {"id": 506, "tier": "Gold", "category": "Quest"},
        ],
        "lootData": [
            {
                "id": 101,
                "itemType": "Equipment",
                "itemId": 201,
                "lootBoxId": 501,
                "percentageChance": 50,
            },
            {
                "id": 102,
                "itemType": "Equipment",
                "itemId": 202,
                "lootBoxId": 503,
                "percentageChance": 10,
            },
            {
                "id": 103,
                "itemType": "Equipment",
                "itemId": 203,
                "lootBoxId": 503,
                "percentageChance": 10,
            },
            {
                "id": 104,
                "itemType": "Equipment",
                "itemId": 204,
                "lootBoxId": 505,
                "percentageChance": 50,
            },
            {
                "id": 105,
                "itemType": "Equipment",
                "itemId": 205,
                "lootBoxId": 505,
                "percentageChance": 50,
            },
            {
                "id": 201,
                "itemType": "Consumable",
                "itemId": 203,
                "lootBoxId": 501,
                "percentageChance": 100,
            },
            {
                "id": 202,
                "itemType": "Consumable",
                "itemId": 203,
                "lootBoxId": 502,
                "percentageChance": 100,
            },
            {
                "id": 203,
                "itemType": "Consumable",
                "itemId": 203,
                "lootBoxId": 503,
                "percentageChance": 100,
            },
            {
                "id": 204,
                "itemType": "Consumable",
                "itemId": 203,
                "lootBoxId": 504,
                "percentageChance": 100,
            },
        ],
        "locations": [
            {"id": 100, "type": "BetaLocation", "name": "Alleyway", "floors": [1]},
            {
                "id": 101,
                "type": "SafeRoom",
                "name": "Peruvian Taco Bell",
                "floors": [1, 2],
            },
            {
                "id": 102,
                "type": "SafeRoom",
                "name": "DMV waiting room",
                "floors": [1, 2],
            },
            {
                "id": 103,
                "type": "Club",
                "name": "Tutorial Guild",
                "floors": [1, 2],
            },
            {
                "id": 104,
                "type": "Stairwell",
                "name": "Stairwell 1-1",
                "floors": [1],
            },
            {
                "id": 105,
                "type": "Stairwell",
                "name": "Stairwell 1-2",
                "floors": [1],
            },
            {
                "id": 201,
                "type": "SafeRoom",
                "name": "French storm shelter",
                "floors": [2, 3],
            },
            {
                "id": 204,
                "type": "Stairwell",
                "name": "Stairwell 2-1",
                "floors": [2],
            },
            {
                "id": 205,
                "type": "Stairwell",
                "name": "Stairwell 2-2",
                "floors": [2],
            },
            {
                "id": 206,
                "type": "Stairwell",
                "name": "Stairwell 2-3",
                "floors": [2],
            },
            {
                "id": 301,
                "type": "Club",
                "name": "Desperado Club",
                "floors": [3, 4, 5],
            },
            {
                "id": 302,
                "type": "Club",
                "name": "Club Vanquisher",
                "floors": [3, 4, 5],
            },
            {
                "id": 303,
                "type": "Stairwell",
                "name": "Stairwell 3-1",
                "floors": [3],
            },
            {
                "id": 304,
                "type": "Stairwell",
                "name": "Stairwell 3-2",
                "floors": [3],
            },
            {
                "id": 401,
                "type": "Stairwell",
                "name": "Stairwell 4-1",
                "floors": [4],
            },
            {
                "id": 402,
                "type": "Stairwell",
                "name": "Stairwell 4-2",
                "floors": [4],
            },
            {
                "id": 501,
                "type": "Stairwell",
                "name": "Stairwell 5-1",
                "floors": [5],
            },
        ],
        "saferooms": [
            {
                "id": 101,
                "hasPersonalSpace": True,
                "stock": ["Consumable:203", "Consumable:204", "MiscItem:205"],
                "manager": 306,
            },
            {
                "id": 102,
            },
            {
                "id": 201,
            },
            {
                # An orphaned saferoom sharing the id of a club
                "id": 301,
                "hasPersonalSpace": True,
                "stock": ["Consumable:203", "Consumable:204"],
            },
        ],
        "clubs": [
            {
                "id": 103,
                "manager": 301,
                "tagline": "Crawlers are recommended to join, but not required",
                "stock": ["Consumable:203", "Consumable:204", "UtilityItem:202"],
            },
            {
                "id": 301,
                "manager": 305,
                "security": [302, 303],
                "tagline": "So fun it hurts",
                "stock": [
                    "Consumable:203",
                    "Consumable:204",
                    "Consumable:209",
                    "UtilityItem:206",
                ],
            },
            {
                "id": 302,
                "tagline": "Heathens will find no solace here",
                "stock": ["UtilityItem:202"],
                "security": [307],
            },
        ],
        "stairwells": [
            {"id": 104},
            {"id": 105},
            {"id": 204},
            {"id": 205},
            {"id": 206},
            {"id": 303},
            {"id": 304},
            {"id": 401},
            {"id": 402},
            {"id": 501},
        ],
        # A Location type without a field plan, which should return null
        "betaLocations": [{"id": 100}],
    }


# --- Helper to find by id (returns None if not found, like JS Array.find) ---


def _find_by_id(collection: list[dict], id: int) -> dict | None:
    for item in collection:
        if item["id"] == id:
            return item
    return None


# --- Batch loader functions ---

# LoadOneCallback pattern: (ids, extra) -> list[T | None]
# LoadManyCallback pattern: (ids, extra) -> list[list[T] | None]
# extra is a dict with key "shared" containing the Database


def batch_get_crawler_by_id(
    ids: list[int], extra: dict
) -> list[CrawlerData | None]:
    data: Database = extra["shared"]
    return [_find_by_id(data["crawlers"], id) for id in ids]


def batch_get_crawlers_by_ids(
    ids_list: list[list[int]], extra: dict
) -> list[list[CrawlerData | None] | None]:
    data: Database = extra["shared"]
    return [
        [_find_by_id(data["crawlers"], id) for id in ids] for ids in ids_list
    ]


def batch_get_npc_by_id(
    ids: list[int], extra: dict
) -> list[NpcData | None]:
    data: Database = extra["shared"]
    return [_find_by_id(data["npcs"], id) for id in ids]


def batch_get_npcs_by_ids(
    ids_list: list[list[int]], extra: dict
) -> list[list[NpcData | None] | None]:
    data: Database = extra["shared"]
    return [
        [_find_by_id(data["npcs"], id) for id in ids] for ids in ids_list
    ]


def batch_get_equipment_by_id(
    ids: list[int], extra: dict
) -> list[EquipmentData | None]:
    data: Database = extra["shared"]
    return [_find_by_id(data["equipment"], id) for id in ids]


def batch_get_consumable_by_id(
    ids: list[int], extra: dict
) -> list[ConsumableData | None]:
    data: Database = extra["shared"]
    return [_find_by_id(data["consumables"], id) for id in ids]


def batch_get_utility_item_by_id(
    ids: list[int], extra: dict
) -> list[UtilityItemData | None]:
    data: Database = extra["shared"]
    return [_find_by_id(data["utilityItems"], id) for id in ids]


def batch_get_misc_item_by_id(
    ids: list[int], extra: dict
) -> list[MiscItemData | None]:
    data: Database = extra["shared"]
    return [_find_by_id(data["miscItems"], id) for id in ids]


def batch_get_locations_by_floor_number(
    floor_number_list: list[int], extra: dict
) -> list[list[LocationData] | None]:
    data: Database = extra["shared"]
    return [
        [c for c in data["locations"] if floor_number in c["floors"]]
        for floor_number in floor_number_list
    ]


def batch_get_location_by_id(
    ids: list[int], extra: dict
) -> list[LocationData | None]:
    data: Database = extra["shared"]
    return [_find_by_id(data["locations"], id) for id in ids]


def batch_get_safe_room_by_id(
    ids: list[int], extra: dict
) -> list[SafeRoomData | None]:
    data: Database = extra["shared"]
    return [_find_by_id(data["saferooms"], id) for id in ids]


def batch_get_club_by_id(
    ids: list[int], extra: dict
) -> list[ClubData | None]:
    data: Database = extra["shared"]
    return [_find_by_id(data["clubs"], id) for id in ids]


def batch_get_stairwell_by_id(
    ids: list[int], extra: dict
) -> list[StairwellData | None]:
    data: Database = extra["shared"]
    return [_find_by_id(data["stairwells"], id) for id in ids]


def batch_get_beta_location_by_id(
    ids: list[int], extra: dict
) -> list[BetaLocationData | None]:
    data: Database = extra["shared"]
    return [_find_by_id(data["betaLocations"], id) for id in ids]


def batch_get_loot_data_by_item_type_and_id(
    identifiers_list: list[tuple[str, int]], extra: dict
) -> list[list[LootDataData] | None]:
    data: Database = extra["shared"]
    return [
        [
            c
            for c in data["lootData"]
            if c["itemType"] == item_type and c["itemId"] == item_id
        ]
        for item_type, item_id in identifiers_list
    ]


def batch_get_loot_data_by_loot_box_id(
    identifiers_list: list[int], extra: dict
) -> list[list[LootDataData] | None]:
    data: Database = extra["shared"]
    return [
        [c for c in data["lootData"] if c["lootBoxId"] == id]
        for id in identifiers_list
    ]


def batch_get_loot_box_by_id(
    ids: list[int], extra: dict
) -> list[LootBoxData | None]:
    data: Database = extra["shared"]
    return [_find_by_id(data["lootBoxes"], id) for id in ids]


def batch_get_friend_ids_by_crawler_id(
    ids: list[int], extra: dict
) -> list[list[int] | None]:
    data: Database = extra["shared"]
    limit: int | None = extra.get("params", {}).get("limit")
    # NOTE: if you were using an actual database or service,
    # you would do this much more efficiently!
    results: list[list[int] | None] = []
    for id in ids:
        crawler = _find_by_id(data["crawlers"], id)
        if crawler is None:
            results.append(None)
            continue
        friend_ids = crawler.get("friends")
        if friend_ids is None:
            results.append(None)
            continue
        if limit:
            results.append(friend_ids[:limit])
        else:
            results.append(friend_ids)
    return results
