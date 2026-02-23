"""Colony service — manages population cubes, colonization, and colony income.

Colonization rules:
- A player colonizes by executing a COLONIZE action.
- The target hex must be explored and owned by the player.
- The player must have a colony ship on the hex (it is consumed on colonization).
- A population cube must be placed on a specific planet slot.
- The cube type must match the planet type:
    money  planet → orbital cube
    science planet → advanced cube
    materials planet → gauss cube
- The player must have the cube in their supply (player_resources.population_cubes).
- Each planet slot can only hold one cube.

Population growth via INFLUENCE:
- An INFLUENCE action on an owned hex with a planet_slot in payload places a
  population cube on that slot without requiring a colony ship.  This is the
  "upgrade population track" growth path.

Colony income (calculated during upkeep):
- Each occupied planet slot contributes per round:
    regular planet: +1 of its resource type
    advanced planet: +2 of its resource type

Influence cost (upkeep):
- Each hex the player owns costs 1 money per round.
- If the player cannot pay, colonies are removed until solvent (bankruptcy).
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hex_tile import HexTile
from app.models.planet_population import PlanetPopulation
from app.models.player_resources import PlayerResources
from app.models.ship import Ship
from app.models.system import System


# Mapping: planet resource type → required cube type in player supply
CUBE_TYPE_FOR_PLANET: dict[str, str] = {
    "money": "orbital",
    "science": "advanced",
    "materials": "gauss",
}


# ---------------------------------------------------------------------------
# Core validation helper
# ---------------------------------------------------------------------------

async def _validate_and_place_cube(
    db: AsyncSession,
    player_id: int,
    hex_tile_id: int,
    planet_slot: int,
) -> PlanetPopulation:
    """Validate and place a population cube on a planet slot.

    Shared logic used by execute_colonize and execute_population_growth.
    Raises ValueError on any validation failure.
    Returns the new PlanetPopulation row.
    """
    # Fetch the system to get planet definitions
    sys_result = await db.execute(
        select(System).where(System.hex_tile_id == hex_tile_id)
    )
    system = sys_result.scalar_one_or_none()
    if system is None or system.planets is None:
        raise ValueError(f"No system or no planets found for hex {hex_tile_id}")

    planets = system.planets
    if planet_slot < 0 or planet_slot >= len(planets):
        raise ValueError(
            f"Planet slot {planet_slot} out of range (0-{len(planets) - 1}) "
            f"for hex {hex_tile_id}"
        )

    planet = planets[planet_slot]
    planet_type = planet.get("type")
    cube_type = CUBE_TYPE_FOR_PLANET.get(planet_type)
    if cube_type is None:
        raise ValueError(f"Unknown planet type '{planet_type}' for slot {planet_slot}")

    # Enforce: only one cube per planet slot
    existing_result = await db.execute(
        select(PlanetPopulation).where(
            PlanetPopulation.hex_tile_id == hex_tile_id,
            PlanetPopulation.planet_slot == planet_slot,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        raise ValueError(
            f"Planet slot {planet_slot} on hex {hex_tile_id} is already occupied"
        )

    # Enforce: max population = number of planet slots
    occupied_result = await db.execute(
        select(PlanetPopulation).where(
            PlanetPopulation.hex_tile_id == hex_tile_id,
        )
    )
    occupied_count = len(list(occupied_result.scalars().all()))
    if occupied_count >= len(planets):
        raise ValueError(
            f"Hex {hex_tile_id} is at maximum population ({len(planets)} cubes)"
        )

    # Deduct cube from player's supply
    res_result = await db.execute(
        select(PlayerResources).where(PlayerResources.player_id == player_id)
    )
    resources = res_result.scalar_one_or_none()
    if resources is None:
        raise ValueError("Player has no resources record")

    cubes = dict(resources.population_cubes)
    available = cubes.get(cube_type, 0)
    if available <= 0:
        raise ValueError(
            f"No {cube_type} cubes remaining in supply to place on a {planet_type} planet"
        )
    cubes[cube_type] = available - 1
    resources.population_cubes = cubes
    await db.flush()

    # Place the cube on the board
    population = PlanetPopulation(
        hex_tile_id=hex_tile_id,
        planet_slot=planet_slot,
        population_type=cube_type,
        owner_player_id=player_id,
    )
    db.add(population)
    await db.flush()
    return population


# ---------------------------------------------------------------------------
# COLONIZE action
# ---------------------------------------------------------------------------

async def execute_colonize(
    db: AsyncSession,
    game_id: int,
    player_id: int,
    hex_tile_id: int,
    planet_slot: int,
) -> dict:
    """Execute a COLONIZE action.

    Requires a colony ship owned by the player on the target hex.
    The colony ship is consumed (destroyed) on use.

    Returns a summary dict.
    Raises ValueError on validation failure.
    """
    # Validate hex exists, is explored, and is owned by the player
    hex_result = await db.execute(
        select(HexTile).where(HexTile.id == hex_tile_id)
    )
    hex_tile = hex_result.scalar_one_or_none()
    if hex_tile is None:
        raise ValueError(f"Hex tile {hex_tile_id} not found")
    if hex_tile.game_id != game_id:
        raise ValueError(f"Hex tile {hex_tile_id} does not belong to this game")
    if not hex_tile.is_explored:
        raise ValueError(f"Hex {hex_tile_id} has not been explored yet")
    if hex_tile.owner_player_id != player_id:
        raise ValueError(
            f"Hex {hex_tile_id} is not owned by you — "
            "you must control a system to colonize it"
        )

    # Require and consume a colony ship on the hex
    colony_ship_result = await db.execute(
        select(Ship).where(
            Ship.game_id == game_id,
            Ship.player_id == player_id,
            Ship.hex_tile_id == hex_tile_id,
            Ship.ship_type == "colony_ship",
        ).limit(1)
    )
    colony_ship = colony_ship_result.scalar_one_or_none()
    if colony_ship is None:
        raise ValueError(
            f"No colony ship found on hex {hex_tile_id} — "
            "you need a colony ship at the target system to colonize"
        )

    # Place the population cube (validates planet slot, cube type, supply)
    population = await _validate_and_place_cube(db, player_id, hex_tile_id, planet_slot)

    # Consume (destroy) the colony ship
    await db.delete(colony_ship)
    await db.flush()

    sys_result = await db.execute(
        select(System).where(System.hex_tile_id == hex_tile_id)
    )
    system = sys_result.scalar_one_or_none()
    planet_type = system.planets[planet_slot]["type"] if system else "unknown"

    return {
        "hex_tile_id": hex_tile_id,
        "planet_slot": planet_slot,
        "cube_type": population.population_type,
        "planet_type": planet_type,
        "colony_ship_consumed": True,
    }


# ---------------------------------------------------------------------------
# Population growth via INFLUENCE
# ---------------------------------------------------------------------------

async def execute_population_growth(
    db: AsyncSession,
    game_id: int,
    player_id: int,
    hex_tile_id: int,
    planet_slot: int,
) -> dict:
    """Place a population cube on an owned hex via the INFLUENCE action.

    No colony ship required — this represents growing the population through
    administrative influence rather than sending colonists.

    Returns a summary dict.
    Raises ValueError on validation failure.
    """
    hex_result = await db.execute(
        select(HexTile).where(HexTile.id == hex_tile_id)
    )
    hex_tile = hex_result.scalar_one_or_none()
    if hex_tile is None:
        raise ValueError(f"Hex tile {hex_tile_id} not found")
    if hex_tile.game_id != game_id:
        raise ValueError(f"Hex tile {hex_tile_id} does not belong to this game")
    if not hex_tile.is_explored:
        raise ValueError(f"Hex {hex_tile_id} has not been explored yet")
    if hex_tile.owner_player_id != player_id:
        raise ValueError(
            f"Hex {hex_tile_id} is not owned by you"
        )

    population = await _validate_and_place_cube(db, player_id, hex_tile_id, planet_slot)

    sys_result = await db.execute(
        select(System).where(System.hex_tile_id == hex_tile_id)
    )
    system = sys_result.scalar_one_or_none()
    planet_type = system.planets[planet_slot]["type"] if system else "unknown"

    return {
        "hex_tile_id": hex_tile_id,
        "planet_slot": planet_slot,
        "cube_type": population.population_type,
        "planet_type": planet_type,
        "colony_ship_consumed": False,
    }


# ---------------------------------------------------------------------------
# Colony income calculation
# ---------------------------------------------------------------------------

async def calculate_colony_income(
    db: AsyncSession, player_id: int
) -> dict[str, int]:
    """Calculate resource income from all population cubes owned by the player.

    Returns {"money": N, "science": N, "materials": N}.
    Advanced planets contribute 2 of their resource type; regular contribute 1.
    """
    pop_result = await db.execute(
        select(PlanetPopulation).where(PlanetPopulation.owner_player_id == player_id)
    )
    populations = list(pop_result.scalars().all())

    income: dict[str, int] = {"money": 0, "science": 0, "materials": 0}

    for pop in populations:
        sys_result = await db.execute(
            select(System).where(System.hex_tile_id == pop.hex_tile_id)
        )
        system = sys_result.scalar_one_or_none()
        if system is None or system.planets is None:
            continue
        if pop.planet_slot >= len(system.planets):
            continue

        planet = system.planets[pop.planet_slot]
        ptype = planet.get("type")
        if ptype not in income:
            continue
        multiplier = 2 if planet.get("advanced") else 1
        income[ptype] += multiplier

    return income


# ---------------------------------------------------------------------------
# Colony disc count (for influence upkeep)
# ---------------------------------------------------------------------------

async def count_colony_discs_for_player(db: AsyncSession, player_id: int) -> int:
    """Return the number of influence discs the player has placed as colony hexes.

    Homeworld and starting_sector tiles are the player's starting empire and do not
    cost additional influence maintenance.  Only inner/outer/galactic_center tiles
    explicitly claimed via INFLUENCE count toward the upkeep maintenance cost.
    """
    from app.models.hex_tile import TileType

    result = await db.execute(
        select(HexTile).where(
            HexTile.owner_player_id == player_id,
            HexTile.tile_type.in_([
                TileType.inner,
                TileType.outer,
                TileType.galactic_center,
            ]),
        )
    )
    owned = list(result.scalars().all())
    return len(owned)


# ---------------------------------------------------------------------------
# Population removal (for combat and bankruptcy)
# ---------------------------------------------------------------------------

async def remove_population_from_hex(db: AsyncSession, hex_tile_id: int) -> int:
    """Remove all population cubes from a hex tile and return them to their owners' supplies.

    Used when an attacker captures a hex (combat) — attackers may place their
    own population afterward by calling execute_colonize or execute_population_growth.

    Returns the number of cubes removed.
    """
    pop_result = await db.execute(
        select(PlanetPopulation).where(PlanetPopulation.hex_tile_id == hex_tile_id)
    )
    populations = list(pop_result.scalars().all())

    # Return cubes to each owner's supply
    for pop in populations:
        res_result = await db.execute(
            select(PlayerResources).where(PlayerResources.player_id == pop.owner_player_id)
        )
        resources = res_result.scalar_one_or_none()
        if resources is not None:
            cubes = dict(resources.population_cubes)
            cubes[pop.population_type] = cubes.get(pop.population_type, 0) + 1
            resources.population_cubes = cubes

    # Delete all population cubes from the hex
    await db.execute(
        delete(PlanetPopulation).where(PlanetPopulation.hex_tile_id == hex_tile_id)
    )
    await db.flush()
    return len(populations)


async def remove_one_colony_for_bankruptcy(
    db: AsyncSession, player_id: int
) -> bool:
    """Remove the player's influence disc from one claimed hex during bankruptcy.

    Only considers inner/outer/galactic_center hexes (explicitly claimed via
    INFLUENCE) — homeworld and starting_sector tiles cannot be relinquished via
    bankruptcy.

    Removes population cubes from that hex and returns them to supply.
    Returns True if a hex was removed, False if the player has no eligible colonies.
    """
    from app.models.hex_tile import TileType

    result = await db.execute(
        select(HexTile).where(
            HexTile.owner_player_id == player_id,
            HexTile.tile_type.in_([
                TileType.inner,
                TileType.outer,
                TileType.galactic_center,
            ]),
        ).limit(1)
    )
    hex_tile = result.scalar_one_or_none()
    if hex_tile is None:
        return False

    # Remove all population from that hex and return cubes to supply
    await remove_population_from_hex(db, hex_tile.id)

    # Relinquish ownership
    hex_tile.owner_player_id = None
    await db.flush()
    return True
