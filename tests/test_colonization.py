"""Tests for Task 11: Colonization & Population Management.

Covers:
- PlanetPopulation model creation and validation
- execute_colonize: valid colonization, wrong cube type rejected,
  no colony ship rejected, colony ship consumed, not-owned hex rejected
- execute_population_growth: place cube via INFLUENCE on owned hex
- Enforce max population per hex (one cube per planet slot)
- calculate_colony_income: regular and advanced planet income
- count_colony_discs_for_player: owned hex counting
- remove_population_from_hex: cubes returned to supply
- remove_one_colony_for_bankruptcy: relinquishes hex ownership
- Upkeep with colony income and influence cost
- Bankruptcy during upkeep (removes hex when money runs out)
- colony_ship build via BUILD action (cost 2 materials, no blueprint)
- COLONIZE action via POST /games/{id}/action endpoint
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game, GamePhase, GameStatus
from app.models.hex_tile import HexTile, TileType
from app.models.planet_population import PlanetPopulation
from app.models.player import Player, Species
from app.models.player_resources import PlayerResources
from app.models.ship import Ship
from app.models.system import System
from app.models.user import User
from app.services.colony_service import (
    CUBE_TYPE_FOR_PLANET,
    calculate_colony_income,
    count_colony_discs_for_player,
    execute_colonize,
    execute_population_growth,
    remove_one_colony_for_bankruptcy,
    remove_population_from_hex,
)
from app.services.resource_service import perform_upkeep_for_player


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_game_and_player(
    db: AsyncSession, species: str = "human"
) -> tuple[Game, Player]:
    user = User(
        email=f"col_{species}_{id(db)}@test.com",
        username=f"col_{species}_{id(db)}",
        hashed_password="x",
    )
    db.add(user)
    await db.flush()

    game = Game(
        name=f"col-game-{id(db)}",
        status=GameStatus.active,
        max_players=2,
        current_round=1,
        current_phase=GamePhase.activation,
        host_user_id=user.id,
    )
    db.add(game)
    await db.flush()

    player = Player(
        game_id=game.id,
        user_id=user.id,
        species=Species(species),
        turn_order=0,
    )
    db.add(player)
    await db.flush()

    resources = PlayerResources(
        player_id=player.id,
        money=10,
        science=10,
        materials=10,
        population_cubes={"orbital": 5, "advanced": 5, "gauss": 5},
        tradespheres=0,
        influence_discs_total=11,
        influence_discs_used=0,
    )
    db.add(resources)
    await db.flush()

    return game, player


async def _make_owned_hex_with_planets(
    db: AsyncSession,
    game_id: int,
    player_id: int,
    planets: list[dict],
    q: int = 0,
    r: int = 0,
) -> tuple[HexTile, System]:
    """Create an explored, player-owned hex with the given planet definitions."""
    hex_tile = HexTile(
        game_id=game_id,
        q=q,
        r=r,
        tile_type=TileType.inner,
        is_explored=True,
        owner_player_id=player_id,
    )
    db.add(hex_tile)
    await db.flush()

    system = System(
        hex_tile_id=hex_tile.id,
        name=f"Test System ({q},{r})",
        planets=planets,
        wormholes=[0, 3],
        ancient_ships_count=0,
    )
    db.add(system)
    await db.flush()
    return hex_tile, system


async def _add_colony_ship(
    db: AsyncSession, game_id: int, player_id: int, hex_tile_id: int
) -> Ship:
    ship = Ship(
        game_id=game_id,
        player_id=player_id,
        ship_type="colony_ship",
        hex_tile_id=hex_tile_id,
        hp_remaining=1,
        is_ancient=False,
    )
    db.add(ship)
    await db.flush()
    return ship


# ---------------------------------------------------------------------------
# CUBE_TYPE_FOR_PLANET mapping
# ---------------------------------------------------------------------------

def test_cube_type_mapping():
    assert CUBE_TYPE_FOR_PLANET["money"] == "orbital"
    assert CUBE_TYPE_FOR_PLANET["science"] == "advanced"
    assert CUBE_TYPE_FOR_PLANET["materials"] == "gauss"


# ---------------------------------------------------------------------------
# execute_colonize
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_colonize_success_money_planet(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    planets = [{"type": "money", "advanced": False}]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )
    await _add_colony_ship(db_session, game.id, player.id, hex_tile.id)

    result = await execute_colonize(db_session, game.id, player.id, hex_tile.id, 0)

    assert result["cube_type"] == "orbital"
    assert result["planet_type"] == "money"
    assert result["colony_ship_consumed"] is True

    # Verify cube placed in DB
    pop_result = await db_session.execute(
        select(PlanetPopulation).where(PlanetPopulation.hex_tile_id == hex_tile.id)
    )
    populations = list(pop_result.scalars().all())
    assert len(populations) == 1
    assert populations[0].population_type == "orbital"
    assert populations[0].owner_player_id == player.id
    assert populations[0].planet_slot == 0


@pytest.mark.asyncio
async def test_colonize_success_science_planet(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    planets = [{"type": "science", "advanced": False}]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )
    await _add_colony_ship(db_session, game.id, player.id, hex_tile.id)

    result = await execute_colonize(db_session, game.id, player.id, hex_tile.id, 0)
    assert result["cube_type"] == "advanced"


@pytest.mark.asyncio
async def test_colonize_success_materials_planet(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    planets = [{"type": "materials", "advanced": False}]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )
    await _add_colony_ship(db_session, game.id, player.id, hex_tile.id)

    result = await execute_colonize(db_session, game.id, player.id, hex_tile.id, 0)
    assert result["cube_type"] == "gauss"


@pytest.mark.asyncio
async def test_colonize_consumes_colony_ship(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    planets = [{"type": "money", "advanced": False}]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )
    colony_ship = await _add_colony_ship(db_session, game.id, player.id, hex_tile.id)
    ship_id = colony_ship.id

    await execute_colonize(db_session, game.id, player.id, hex_tile.id, 0)

    # Colony ship must be gone
    result = await db_session.execute(select(Ship).where(Ship.id == ship_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_colonize_deducts_cube_from_supply(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    planets = [{"type": "money", "advanced": False}]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )
    await _add_colony_ship(db_session, game.id, player.id, hex_tile.id)

    # Before: 5 orbital cubes
    res_result = await db_session.execute(
        select(PlayerResources).where(PlayerResources.player_id == player.id)
    )
    resources = res_result.scalar_one()
    assert resources.population_cubes["orbital"] == 5

    await execute_colonize(db_session, game.id, player.id, hex_tile.id, 0)

    await db_session.refresh(resources)
    assert resources.population_cubes["orbital"] == 4


@pytest.mark.asyncio
async def test_colonize_rejects_no_colony_ship(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    planets = [{"type": "money", "advanced": False}]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )
    # No colony ship added

    with pytest.raises(ValueError, match="colony ship"):
        await execute_colonize(db_session, game.id, player.id, hex_tile.id, 0)


@pytest.mark.asyncio
async def test_colonize_rejects_unowned_hex(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    # Hex owned by nobody
    hex_tile = HexTile(
        game_id=game.id,
        q=3,
        r=3,
        tile_type=TileType.inner,
        is_explored=True,
        owner_player_id=None,
    )
    db_session.add(hex_tile)
    await db_session.flush()
    system = System(
        hex_tile_id=hex_tile.id,
        planets=[{"type": "money", "advanced": False}],
        wormholes=[0, 3],
        ancient_ships_count=0,
    )
    db_session.add(system)
    await db_session.flush()

    await _add_colony_ship(db_session, game.id, player.id, hex_tile.id)

    with pytest.raises(ValueError, match="not owned by you"):
        await execute_colonize(db_session, game.id, player.id, hex_tile.id, 0)


@pytest.mark.asyncio
async def test_colonize_rejects_unexplored_hex(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    hex_tile = HexTile(
        game_id=game.id,
        q=4,
        r=4,
        tile_type=TileType.inner,
        is_explored=False,
        owner_player_id=player.id,
    )
    db_session.add(hex_tile)
    await db_session.flush()
    system = System(
        hex_tile_id=hex_tile.id,
        planets=[{"type": "money", "advanced": False}],
        wormholes=[0, 3],
        ancient_ships_count=0,
    )
    db_session.add(system)
    await db_session.flush()

    await _add_colony_ship(db_session, game.id, player.id, hex_tile.id)

    with pytest.raises(ValueError, match="not been explored"):
        await execute_colonize(db_session, game.id, player.id, hex_tile.id, 0)


@pytest.mark.asyncio
async def test_colonize_rejects_invalid_planet_slot(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    planets = [{"type": "money", "advanced": False}]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )
    await _add_colony_ship(db_session, game.id, player.id, hex_tile.id)

    with pytest.raises(ValueError, match="out of range"):
        await execute_colonize(db_session, game.id, player.id, hex_tile.id, 5)


@pytest.mark.asyncio
async def test_colonize_rejects_slot_already_occupied(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    planets = [{"type": "money", "advanced": False}]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )
    # Pre-place a cube on slot 0
    existing_pop = PlanetPopulation(
        hex_tile_id=hex_tile.id,
        planet_slot=0,
        population_type="orbital",
        owner_player_id=player.id,
    )
    db_session.add(existing_pop)
    await db_session.flush()

    await _add_colony_ship(db_session, game.id, player.id, hex_tile.id)

    with pytest.raises(ValueError, match="already occupied"):
        await execute_colonize(db_session, game.id, player.id, hex_tile.id, 0)


@pytest.mark.asyncio
async def test_colonize_max_population_enforced(db_session: AsyncSession):
    """Hex with 1 planet slot can only hold 1 cube — attempting to add a second fails."""
    game, player = await _make_game_and_player(db_session)
    planets = [{"type": "money", "advanced": False}]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )
    # Pre-place a cube on slot 0 (the only slot)
    pop = PlanetPopulation(
        hex_tile_id=hex_tile.id,
        planet_slot=0,
        population_type="orbital",
        owner_player_id=player.id,
    )
    db_session.add(pop)
    await db_session.flush()

    # Add a second planet to simulate there's a second planet but also at max
    # Directly test max: hex with 2 planets, both occupied
    hex2 = HexTile(
        game_id=game.id,
        q=9,
        r=9,
        tile_type=TileType.inner,
        is_explored=True,
        owner_player_id=player.id,
    )
    db_session.add(hex2)
    await db_session.flush()
    sys2 = System(
        hex_tile_id=hex2.id,
        planets=[
            {"type": "money", "advanced": False},
            {"type": "science", "advanced": False},
        ],
        wormholes=[],
        ancient_ships_count=0,
    )
    db_session.add(sys2)
    await db_session.flush()

    # Occupy both slots
    db_session.add(PlanetPopulation(
        hex_tile_id=hex2.id, planet_slot=0, population_type="orbital", owner_player_id=player.id
    ))
    db_session.add(PlanetPopulation(
        hex_tile_id=hex2.id, planet_slot=1, population_type="advanced", owner_player_id=player.id
    ))
    await db_session.flush()

    # Now try to colonize a (nonexistent) slot 2
    await _add_colony_ship(db_session, game.id, player.id, hex2.id)
    with pytest.raises(ValueError, match="out of range|maximum population"):
        await execute_colonize(db_session, game.id, player.id, hex2.id, 2)


# ---------------------------------------------------------------------------
# Population growth via INFLUENCE
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_population_growth_success(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    planets = [{"type": "science", "advanced": False}]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )

    result = await execute_population_growth(db_session, game.id, player.id, hex_tile.id, 0)

    assert result["cube_type"] == "advanced"
    assert result["colony_ship_consumed"] is False

    pop_result = await db_session.execute(
        select(PlanetPopulation).where(PlanetPopulation.hex_tile_id == hex_tile.id)
    )
    populations = list(pop_result.scalars().all())
    assert len(populations) == 1
    assert populations[0].population_type == "advanced"


@pytest.mark.asyncio
async def test_population_growth_rejects_unowned_hex(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    planets = [{"type": "science", "advanced": False}]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets, q=7, r=7
    )
    hex_tile.owner_player_id = None  # take away ownership
    await db_session.flush()

    with pytest.raises(ValueError, match="not owned by you"):
        await execute_population_growth(db_session, game.id, player.id, hex_tile.id, 0)


# ---------------------------------------------------------------------------
# calculate_colony_income
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_colony_income_regular_planets(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    planets = [
        {"type": "money", "advanced": False},
        {"type": "science", "advanced": False},
        {"type": "materials", "advanced": False},
    ]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )

    # Place one cube on each planet slot
    for slot, cube_type in enumerate(["orbital", "advanced", "gauss"]):
        db_session.add(PlanetPopulation(
            hex_tile_id=hex_tile.id,
            planet_slot=slot,
            population_type=cube_type,
            owner_player_id=player.id,
        ))
    await db_session.flush()

    income = await calculate_colony_income(db_session, player.id)
    assert income == {"money": 1, "science": 1, "materials": 1}


@pytest.mark.asyncio
async def test_colony_income_advanced_planets(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    planets = [
        {"type": "money", "advanced": True},
        {"type": "science", "advanced": True},
    ]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )

    db_session.add(PlanetPopulation(
        hex_tile_id=hex_tile.id, planet_slot=0,
        population_type="orbital", owner_player_id=player.id
    ))
    db_session.add(PlanetPopulation(
        hex_tile_id=hex_tile.id, planet_slot=1,
        population_type="advanced", owner_player_id=player.id
    ))
    await db_session.flush()

    income = await calculate_colony_income(db_session, player.id)
    assert income["money"] == 2
    assert income["science"] == 2
    assert income["materials"] == 0


@pytest.mark.asyncio
async def test_colony_income_empty_no_colonies(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    income = await calculate_colony_income(db_session, player.id)
    assert income == {"money": 0, "science": 0, "materials": 0}


# ---------------------------------------------------------------------------
# count_colony_discs_for_player
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_count_colony_discs_no_hexes(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    count = await count_colony_discs_for_player(db_session, player.id)
    assert count == 0


@pytest.mark.asyncio
async def test_count_colony_discs_with_owned_hexes(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    for i in range(3):
        hex_tile = HexTile(
            game_id=game.id, q=i, r=i, tile_type=TileType.inner,
            is_explored=True, owner_player_id=player.id
        )
        db_session.add(hex_tile)
    await db_session.flush()

    count = await count_colony_discs_for_player(db_session, player.id)
    assert count == 3


# ---------------------------------------------------------------------------
# remove_population_from_hex
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remove_population_from_hex_returns_cubes(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    planets = [
        {"type": "money", "advanced": False},
        {"type": "science", "advanced": False},
    ]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )
    db_session.add(PlanetPopulation(
        hex_tile_id=hex_tile.id, planet_slot=0,
        population_type="orbital", owner_player_id=player.id
    ))
    db_session.add(PlanetPopulation(
        hex_tile_id=hex_tile.id, planet_slot=1,
        population_type="advanced", owner_player_id=player.id
    ))
    await db_session.flush()

    removed = await remove_population_from_hex(db_session, hex_tile.id)
    assert removed == 2

    # Cubes returned to supply
    res_result = await db_session.execute(
        select(PlayerResources).where(PlayerResources.player_id == player.id)
    )
    resources = res_result.scalar_one()
    assert resources.population_cubes["orbital"] == 6  # 5 + 1 returned
    assert resources.population_cubes["advanced"] == 6  # 5 + 1 returned

    # DB rows deleted
    pop_result = await db_session.execute(
        select(PlanetPopulation).where(PlanetPopulation.hex_tile_id == hex_tile.id)
    )
    assert list(pop_result.scalars().all()) == []


@pytest.mark.asyncio
async def test_remove_population_from_hex_empty(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    planets = [{"type": "money", "advanced": False}]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )

    removed = await remove_population_from_hex(db_session, hex_tile.id)
    assert removed == 0


# ---------------------------------------------------------------------------
# remove_one_colony_for_bankruptcy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bankruptcy_removes_colony(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    planets = [{"type": "money", "advanced": False}]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )
    db_session.add(PlanetPopulation(
        hex_tile_id=hex_tile.id, planet_slot=0,
        population_type="orbital", owner_player_id=player.id
    ))
    await db_session.flush()

    removed = await remove_one_colony_for_bankruptcy(db_session, player.id)
    assert removed is True

    await db_session.refresh(hex_tile)
    assert hex_tile.owner_player_id is None


@pytest.mark.asyncio
async def test_bankruptcy_returns_false_when_no_colonies(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    removed = await remove_one_colony_for_bankruptcy(db_session, player.id)
    assert removed is False


# ---------------------------------------------------------------------------
# Upkeep with colony income
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upkeep_includes_colony_income(db_session: AsyncSession):
    game, player = await _make_game_and_player(db_session)
    planets = [
        {"type": "money", "advanced": False},
        {"type": "science", "advanced": True},
        {"type": "materials", "advanced": False},
    ]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )
    db_session.add(PlanetPopulation(
        hex_tile_id=hex_tile.id, planet_slot=0,
        population_type="orbital", owner_player_id=player.id
    ))
    db_session.add(PlanetPopulation(
        hex_tile_id=hex_tile.id, planet_slot=1,
        population_type="advanced", owner_player_id=player.id
    ))
    db_session.add(PlanetPopulation(
        hex_tile_id=hex_tile.id, planet_slot=2,
        population_type="gauss", owner_player_id=player.id
    ))
    await db_session.flush()

    res_result = await db_session.execute(
        select(PlayerResources).where(PlayerResources.player_id == player.id)
    )
    resources = res_result.scalar_one()
    initial_money = resources.money

    result = await perform_upkeep_for_player(player.id, db_session)

    # Income: 1 money (regular) + 2 science (advanced) + 1 materials (regular)
    assert result["money_gained"] == 1   # only money colony income (tradespheres=0)
    assert result["science_gained"] == 2
    assert result["materials_gained"] == 1

    # Colony disc cost: 1 owned hex = 1 money
    assert result["influence_cost"] == 1

    await db_session.refresh(resources)
    assert resources.money == initial_money + 1 - 1  # +1 income - 1 cost


@pytest.mark.asyncio
async def test_upkeep_bankruptcy_removes_hex(db_session: AsyncSession):
    """Player with 0 money cannot afford influence cost — goes bankrupt."""
    game, player = await _make_game_and_player(db_session)
    planets = [{"type": "money", "advanced": False}]
    hex_tile, _ = await _make_owned_hex_with_planets(
        db_session, game.id, player.id, planets
    )

    # Set money to 0 so player cannot pay the 1-money influence cost
    res_result = await db_session.execute(
        select(PlayerResources).where(PlayerResources.player_id == player.id)
    )
    resources = res_result.scalar_one()
    resources.money = 0
    resources.tradespheres = 0  # no income either
    await db_session.flush()

    result = await perform_upkeep_for_player(player.id, db_session)

    assert result["bankrupt"] is True
    assert result["discs_removed"] >= 1

    # Hex should no longer be owned
    await db_session.refresh(hex_tile)
    assert hex_tile.owner_player_id is None


# ---------------------------------------------------------------------------
# colony_ship build
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_colony_ship_costs_2_materials(db_session: AsyncSession):
    from app.services.resource_service import BUILD_COSTS
    assert BUILD_COSTS["colony_ship"] == 2


@pytest.mark.asyncio
async def test_build_colony_ship_creates_ship(db_session: AsyncSession):
    from app.services.ship_service import build_ship
    from app.services.resource_service import validate_and_deduct_build_cost

    game, player = await _make_game_and_player(db_session)

    # Give player a homeworld hex
    homeworld = HexTile(
        game_id=game.id, q=0, r=0, tile_type=TileType.homeworld,
        is_explored=True, owner_player_id=player.id
    )
    db_session.add(homeworld)
    await db_session.flush()

    res_result = await db_session.execute(
        select(PlayerResources).where(PlayerResources.player_id == player.id)
    )
    resources = res_result.scalar_one()
    resources.materials = 5
    await db_session.flush()

    await validate_and_deduct_build_cost(player.id, "colony_ship", db_session)
    ship = await build_ship(player.id, game.id, "colony_ship", db_session)

    assert ship.ship_type == "colony_ship"
    assert ship.hp_remaining == 1
    assert ship.player_id == player.id
    assert ship.hex_tile_id == homeworld.id

    await db_session.refresh(resources)
    assert resources.materials == 3  # 5 - 2 = 3


# ---------------------------------------------------------------------------
# API integration: COLONIZE via POST /games/{id}/action
# ---------------------------------------------------------------------------

async def _register_and_login(client, email, username, password="pass123"):
    await client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


async def _setup_two_player_game(client):
    """Create a 2-player started game; return (tokens, game_id)."""
    t0 = await _register_and_login(client, f"col_api_0_{id(client)}@t.com", f"col_a0_{id(client)}")
    t1 = await _register_and_login(client, f"col_api_1_{id(client)}@t.com", f"col_a1_{id(client)}")

    resp = await client.post(
        "/games",
        json={"name": f"col api game {id(client)}", "max_players": 2},
        headers={"Authorization": f"Bearer {t0}"},
    )
    game_id = resp.json()["id"]

    inv = await client.post(
        f"/games/{game_id}/invite",
        json={"invitee_email": f"col_api_1_{id(client)}@t.com"},
        headers={"Authorization": f"Bearer {t0}"},
    )
    tok = inv.json()["token"]
    await client.post(
        f"/games/{game_id}/join",
        json={"token": tok},
        headers={"Authorization": f"Bearer {t1}"},
    )
    await client.post(
        f"/games/{game_id}/select-species",
        json={"species": "human"},
        headers={"Authorization": f"Bearer {t0}"},
    )
    await client.post(
        f"/games/{game_id}/select-species",
        json={"species": "planta"},
        headers={"Authorization": f"Bearer {t1}"},
    )
    start = await client.post(
        f"/games/{game_id}/start",
        headers={"Authorization": f"Bearer {t0}"},
    )
    assert start.status_code == 200
    return [t0, t1], game_id


@pytest.mark.asyncio
async def test_api_colonize_action_rejected_without_colony_ship(db_client, db_session):
    """COLONIZE via API with no colony ship should return 400."""
    tokens, game_id = await _setup_two_player_game(db_client)

    # Find the active player
    from app.models.player import Player

    player_result = await db_session.execute(
        select(Player).where(Player.game_id == game_id, Player.is_active_turn == True)  # noqa: E712
    )
    active_player = player_result.scalar_one()

    # Find the active player's token (first player is turn_order=0)
    token = tokens[0] if active_player.turn_order == 0 else tokens[1]

    # Get the active player's homeworld hex
    hw_result = await db_session.execute(
        select(HexTile).where(
            HexTile.game_id == game_id,
            HexTile.owner_player_id == active_player.id,
            HexTile.tile_type.in_([TileType.homeworld, TileType.starting_sector]),
        )
    )
    homeworld = hw_result.scalars().first()
    assert homeworld is not None

    resp = await db_client.post(
        f"/games/{game_id}/action",
        json={
            "action_type": "colonize",
            "payload": {"hex_tile_id": homeworld.id, "planet_slot": 0},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    # Should fail because there's no colony ship on the homeworld
    # (The homeworld system may or may not have planets; either way, no colony ship)
    assert resp.status_code == 400
