"""
Static definitions for all Eclipse: Second Dawn system tiles.

Axial coordinate direction encoding (pointy-top hexagons):
  Direction 0: (q+1, r  ) - East
  Direction 1: (q+1, r-1) - North-East
  Direction 2: (q,   r-1) - North-West
  Direction 3: (q-1, r  ) - West
  Direction 4: (q-1, r+1) - South-West
  Direction 5: (q,   r+1) - South-East

Opposite of direction d is (d + 3) % 6.

Wormhole alignment rule: if tile A at (q1,r1) has a wormhole in direction d,
and tile B is the neighbor in direction d, tile B must have a wormhole in
direction (d + 3) % 6 for a valid wormhole connection.
"""

from dataclasses import dataclass, field


@dataclass
class Planet:
    type: str  # "money", "science", "materials"
    advanced: bool = False


@dataclass
class SystemTile:
    tile_id: str
    name: str
    tile_category: str  # "galactic_center", "inner", "outer", "homeworld", "starting_sector"
    planets: list[Planet] = field(default_factory=list)
    # Wormhole directions (0-5) relative to tile with no rotation
    wormholes: list[int] = field(default_factory=list)
    ancient_ships_count: int = 0
    has_discovery: bool = True  # most non-homeworld tiles have a discovery tile


# ---------------------------------------------------------------------------
# Galactic Center
# ---------------------------------------------------------------------------

GALACTIC_CENTER = SystemTile(
    tile_id="GC",
    name="Galactic Center",
    tile_category="galactic_center",
    planets=[],
    wormholes=[0, 1, 2, 3, 4, 5],  # Open in all directions
    ancient_ships_count=1,  # GCDS (Galactic Center Defense System)
    has_discovery=False,
)

# ---------------------------------------------------------------------------
# Inner ring tiles (placed in ring 1 around Galactic Center)
# Each has 2-4 wormholes and 0-3 planets.
# ---------------------------------------------------------------------------

INNER_RING_TILES: list[SystemTile] = [
    SystemTile(
        tile_id="I01",
        name="Tau Ceti",
        tile_category="inner",
        planets=[Planet("money"), Planet("science")],
        wormholes=[0, 3],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="I02",
        name="Alpha Centauri",
        tile_category="inner",
        planets=[Planet("materials"), Planet("money")],
        wormholes=[1, 4],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="I03",
        name="Barnard's Star",
        tile_category="inner",
        planets=[Planet("science"), Planet("materials")],
        wormholes=[2, 5],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="I04",
        name="Wolf 359",
        tile_category="inner",
        planets=[Planet("money", advanced=True)],
        wormholes=[0, 1, 3],
        ancient_ships_count=2,
    ),
    SystemTile(
        tile_id="I05",
        name="Lalande 21185",
        tile_category="inner",
        planets=[Planet("science", advanced=True), Planet("materials")],
        wormholes=[0, 2, 4],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="I06",
        name="Sirius",
        tile_category="inner",
        planets=[Planet("money"), Planet("money")],
        wormholes=[1, 2, 4, 5],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="I07",
        name="Luyten 726-8",
        tile_category="inner",
        planets=[Planet("materials", advanced=True)],
        wormholes=[0, 3],
        ancient_ships_count=2,
    ),
    SystemTile(
        tile_id="I08",
        name="Ross 154",
        tile_category="inner",
        planets=[Planet("science"), Planet("science")],
        wormholes=[1, 4],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="I09",
        name="Ross 248",
        tile_category="inner",
        planets=[Planet("materials"), Planet("materials")],
        wormholes=[2, 5],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="I10",
        name="Epsilon Eridani",
        tile_category="inner",
        planets=[Planet("money"), Planet("science"), Planet("materials")],
        wormholes=[0, 1, 3, 4],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="I11",
        name="Lacaille 9352",
        tile_category="inner",
        planets=[Planet("money", advanced=True), Planet("science")],
        wormholes=[0, 2, 3, 5],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="I12",
        name="EZ Aquarii",
        tile_category="inner",
        planets=[],
        wormholes=[0, 1, 2, 3, 4, 5],
        ancient_ships_count=3,
    ),
    SystemTile(
        tile_id="I13",
        name="Procyon",
        tile_category="inner",
        planets=[Planet("science", advanced=True)],
        wormholes=[1, 2, 4, 5],
        ancient_ships_count=2,
    ),
    SystemTile(
        tile_id="I14",
        name="61 Cygni",
        tile_category="inner",
        planets=[Planet("money"), Planet("materials")],
        wormholes=[0, 3],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="I15",
        name="Struve 2398",
        tile_category="inner",
        planets=[Planet("science")],
        wormholes=[2, 5],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="I16",
        name="Groombridge 34",
        tile_category="inner",
        planets=[Planet("materials", advanced=True), Planet("money")],
        wormholes=[1, 4],
        ancient_ships_count=0,
    ),
]

# ---------------------------------------------------------------------------
# Outer ring tiles (placed in rings 2-3 for larger games)
# ---------------------------------------------------------------------------

OUTER_RING_TILES: list[SystemTile] = [
    SystemTile(
        tile_id="O01",
        name="Epsilon Indi",
        tile_category="outer",
        planets=[Planet("money"), Planet("science")],
        wormholes=[0, 3],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="O02",
        name="Tau Ceti II",
        tile_category="outer",
        planets=[Planet("materials"), Planet("materials")],
        wormholes=[1, 4],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="O03",
        name="Gliese 229",
        tile_category="outer",
        planets=[Planet("science", advanced=True)],
        wormholes=[2, 5],
        ancient_ships_count=2,
    ),
    SystemTile(
        tile_id="O04",
        name="Gliese 570",
        tile_category="outer",
        planets=[Planet("money", advanced=True), Planet("science")],
        wormholes=[0, 2, 3, 5],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="O05",
        name="Fomalhaut",
        tile_category="outer",
        planets=[Planet("money"), Planet("money"), Planet("science")],
        wormholes=[0, 1, 4],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="O06",
        name="Vega",
        tile_category="outer",
        planets=[Planet("science"), Planet("materials")],
        wormholes=[0, 3],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="O07",
        name="Altair",
        tile_category="outer",
        planets=[Planet("materials", advanced=True), Planet("materials")],
        wormholes=[1, 4],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="O08",
        name="Deneb",
        tile_category="outer",
        planets=[Planet("money"), Planet("science"), Planet("materials")],
        wormholes=[2, 3, 5],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="O09",
        name="Rigel",
        tile_category="outer",
        planets=[Planet("science", advanced=True), Planet("science")],
        wormholes=[0, 1, 3, 4],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="O10",
        name="Betelgeuse",
        tile_category="outer",
        planets=[],
        wormholes=[0, 1, 2, 3, 4, 5],
        ancient_ships_count=4,
    ),
    SystemTile(
        tile_id="O11",
        name="Capella",
        tile_category="outer",
        planets=[Planet("money", advanced=True)],
        wormholes=[0, 3],
        ancient_ships_count=2,
    ),
    SystemTile(
        tile_id="O12",
        name="Arcturus",
        tile_category="outer",
        planets=[Planet("materials"), Planet("science")],
        wormholes=[1, 2, 4, 5],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="O13",
        name="Spica",
        tile_category="outer",
        planets=[Planet("money"), Planet("materials")],
        wormholes=[0, 3],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="O14",
        name="Antares",
        tile_category="outer",
        planets=[Planet("science"), Planet("science"), Planet("materials")],
        wormholes=[2, 5],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="O15",
        name="Pollux",
        tile_category="outer",
        planets=[Planet("materials", advanced=True), Planet("science")],
        wormholes=[1, 2, 4, 5],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="O16",
        name="Castor",
        tile_category="outer",
        planets=[Planet("money"), Planet("science", advanced=True)],
        wormholes=[0, 1, 3, 4],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="O17",
        name="Regulus",
        tile_category="outer",
        planets=[Planet("materials"), Planet("money")],
        wormholes=[2, 5],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="O18",
        name="Mimosa",
        tile_category="outer",
        planets=[Planet("science"), Planet("materials", advanced=True)],
        wormholes=[0, 3],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="O19",
        name="Acrux",
        tile_category="outer",
        planets=[Planet("money"), Planet("money")],
        wormholes=[1, 4],
        ancient_ships_count=0,
    ),
    SystemTile(
        tile_id="O20",
        name="Gacrux",
        tile_category="outer",
        planets=[Planet("materials", advanced=True)],
        wormholes=[2, 3, 5],
        ancient_ships_count=2,
    ),
]

# ---------------------------------------------------------------------------
# Homeworld tiles (one per species — placed at the outer ring edge)
# Homeworld tiles are always explored and owned by the respective player.
# They have wormholes toward the interior of the map only.
# ---------------------------------------------------------------------------

HOMEWORLD_TILES: dict[str, SystemTile] = {
    "human": SystemTile(
        tile_id="HW_human",
        name="Sol (Human Homeworld)",
        tile_category="homeworld",
        planets=[Planet("money"), Planet("science"), Planet("materials")],
        wormholes=[3],  # Single wormhole pointing inward (adjusted by map generator)
        ancient_ships_count=0,
        has_discovery=False,
    ),
    "eridani_empire": SystemTile(
        tile_id="HW_eridani_empire",
        name="Eridani Prime",
        tile_category="homeworld",
        planets=[Planet("money"), Planet("money"), Planet("materials")],
        wormholes=[3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
    "hydran_progress": SystemTile(
        tile_id="HW_hydran_progress",
        name="Hydra",
        tile_category="homeworld",
        planets=[Planet("money"), Planet("science"), Planet("science")],
        wormholes=[3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
    "planta": SystemTile(
        tile_id="HW_planta",
        name="Planta Nexus",
        tile_category="homeworld",
        planets=[Planet("money"), Planet("science"), Planet("materials")],
        wormholes=[3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
    "descendants_of_draco": SystemTile(
        tile_id="HW_descendants_of_draco",
        name="Draco Prime",
        tile_category="homeworld",
        planets=[Planet("money"), Planet("materials"), Planet("materials")],
        wormholes=[3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
    "mechanema": SystemTile(
        tile_id="HW_mechanema",
        name="Mechanema Core",
        tile_category="homeworld",
        planets=[Planet("materials"), Planet("materials"), Planet("science")],
        wormholes=[3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
    "orion_hegemony": SystemTile(
        tile_id="HW_orion_hegemony",
        name="Orion Prime",
        tile_category="homeworld",
        planets=[Planet("money"), Planet("materials"), Planet("materials")],
        wormholes=[3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
    "exiles": SystemTile(
        tile_id="HW_exiles",
        name="Exile Station",
        tile_category="homeworld",
        planets=[Planet("money"), Planet("science")],
        wormholes=[3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
    "terran_directorate": SystemTile(
        tile_id="HW_terran_directorate",
        name="New Terra",
        tile_category="homeworld",
        planets=[Planet("money"), Planet("science"), Planet("materials")],
        wormholes=[3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
}

# ---------------------------------------------------------------------------
# Starting sector tiles (adjacent to homeworld, between homeworld and inner ring)
# These are pre-explored by the player at game start.
# ---------------------------------------------------------------------------

STARTING_SECTOR_TILES: dict[str, SystemTile] = {
    "human": SystemTile(
        tile_id="SS_human",
        name="Sol System Outskirts",
        tile_category="starting_sector",
        planets=[Planet("money")],
        wormholes=[0, 3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
    "eridani_empire": SystemTile(
        tile_id="SS_eridani_empire",
        name="Eridani Frontier",
        tile_category="starting_sector",
        planets=[Planet("materials")],
        wormholes=[0, 3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
    "hydran_progress": SystemTile(
        tile_id="SS_hydran_progress",
        name="Hydran Expanse",
        tile_category="starting_sector",
        planets=[Planet("science")],
        wormholes=[0, 3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
    "planta": SystemTile(
        tile_id="SS_planta",
        name="Planta Tendrils",
        tile_category="starting_sector",
        planets=[Planet("materials")],
        wormholes=[0, 3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
    "descendants_of_draco": SystemTile(
        tile_id="SS_descendants_of_draco",
        name="Draco Borderlands",
        tile_category="starting_sector",
        planets=[Planet("money")],
        wormholes=[0, 3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
    "mechanema": SystemTile(
        tile_id="SS_mechanema",
        name="Mechanema Forge",
        tile_category="starting_sector",
        planets=[Planet("materials")],
        wormholes=[0, 3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
    "orion_hegemony": SystemTile(
        tile_id="SS_orion_hegemony",
        name="Orion Vanguard",
        tile_category="starting_sector",
        planets=[Planet("money")],
        wormholes=[0, 3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
    "exiles": SystemTile(
        tile_id="SS_exiles",
        name="Exile Drifts",
        tile_category="starting_sector",
        planets=[Planet("science")],
        wormholes=[0, 3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
    "terran_directorate": SystemTile(
        tile_id="SS_terran_directorate",
        name="Terran Perimeter",
        tile_category="starting_sector",
        planets=[Planet("science")],
        wormholes=[0, 3],
        ancient_ships_count=0,
        has_discovery=False,
    ),
}

# Convenience lookup by tile_id (all keys are tile_id strings like "GC", "I01", "HW_human")
ALL_TILES: dict[str, SystemTile] = {
    GALACTIC_CENTER.tile_id: GALACTIC_CENTER,
    **{t.tile_id: t for t in INNER_RING_TILES},
    **{t.tile_id: t for t in OUTER_RING_TILES},
    **{t.tile_id: t for t in HOMEWORLD_TILES.values()},
    **{t.tile_id: t for t in STARTING_SECTOR_TILES.values()},
}


def get_tile(tile_id: str) -> SystemTile:
    return ALL_TILES[tile_id]
