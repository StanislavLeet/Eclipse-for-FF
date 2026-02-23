"""Static definitions for Eclipse: Second Dawn discovery tiles.

When a player explores an unexplored sector, they draw a discovery tile.
Most tiles give a positive effect (resources, ancient ships, VP orbitals).
Some tiles are empty (no effect).

Tiles are shuffled into a deck at game start.  Each game gets one copy
of every template defined here.  The deck is persisted in the DB so draws
are reproducible.
"""

from dataclasses import dataclass


@dataclass
class DiscoveryTileTemplate:
    discovery_id: str
    name: str
    # Effect category:
    #   "money"          -> add effect_value money to player
    #   "science"        -> add effect_value science
    #   "materials"      -> add effect_value materials
    #   "ancient_cruiser"-> give player an ancient cruiser ship (reprogrammed)
    #   "orbital"        -> award effect_value VP (tracked on player.vp_count)
    #   "empty"          -> no effect
    effect_type: str
    effect_value: int = 0
    positive: bool = True   # False means the tile is an empty/bad result


# ---------------------------------------------------------------------------
# Discovery tile templates (18 tiles total — same scale as the real game)
# ---------------------------------------------------------------------------

DISCOVERY_TILE_TEMPLATES: list[DiscoveryTileTemplate] = [
    # Money tiles (3)
    DiscoveryTileTemplate("disc_money_2a", "+2 Money Cache",    "money",     2, True),
    DiscoveryTileTemplate("disc_money_2b", "+2 Money Cache",    "money",     2, True),
    DiscoveryTileTemplate("disc_money_3",  "+3 Money Vault",    "money",     3, True),
    # Science tiles (3)
    DiscoveryTileTemplate("disc_science_2a", "+2 Science Lab",  "science",   2, True),
    DiscoveryTileTemplate("disc_science_2b", "+2 Science Lab",  "science",   2, True),
    DiscoveryTileTemplate("disc_science_3",  "+3 Research Cache","science",  3, True),
    # Materials tiles (3)
    DiscoveryTileTemplate("disc_materials_2a", "+2 Materials",  "materials", 2, True),
    DiscoveryTileTemplate("disc_materials_2b", "+2 Materials",  "materials", 2, True),
    DiscoveryTileTemplate("disc_materials_3",  "+3 Materials",  "materials", 3, True),
    # Ancient cruiser tiles (2) — player gains a derelict ancient cruiser
    DiscoveryTileTemplate("disc_ancient_1", "Derelict Cruiser", "ancient_cruiser", 1, True),
    DiscoveryTileTemplate("disc_ancient_2", "Derelict Cruiser", "ancient_cruiser", 1, True),
    # Orbital VP tiles (2)
    DiscoveryTileTemplate("disc_orbital_1", "Orbital +1VP",     "orbital",   1, True),
    DiscoveryTileTemplate("disc_orbital_2", "Orbital +1VP",     "orbital",   1, True),
    # Empty tiles (5) — nothing happens
    DiscoveryTileTemplate("disc_empty_1", "Empty Space",        "empty",     0, False),
    DiscoveryTileTemplate("disc_empty_2", "Empty Space",        "empty",     0, False),
    DiscoveryTileTemplate("disc_empty_3", "Empty Space",        "empty",     0, False),
    DiscoveryTileTemplate("disc_empty_4", "Empty Space",        "empty",     0, False),
    DiscoveryTileTemplate("disc_empty_5", "Empty Space",        "empty",     0, False),
]

# Lookup by discovery_id
DISCOVERY_TILE_LOOKUP: dict[str, DiscoveryTileTemplate] = {
    t.discovery_id: t for t in DISCOVERY_TILE_TEMPLATES
}


def get_discovery_tile(discovery_id: str) -> DiscoveryTileTemplate:
    """Return a DiscoveryTileTemplate by ID, or raise KeyError."""
    tile = DISCOVERY_TILE_LOOKUP.get(discovery_id)
    if tile is None:
        raise KeyError(f"Unknown discovery tile: '{discovery_id}'")
    return tile
