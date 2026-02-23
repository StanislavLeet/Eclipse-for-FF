"""Resource management service for player economies in Eclipse: Second Dawn."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.species import get_species
from app.models.player import Player
from app.models.player_resources import PlayerResources

# Material cost to build each ship type (standard Eclipse rules)
BUILD_COSTS: dict[str, int] = {
    "interceptor": 3,
    "cruiser": 5,
    "dreadnought": 8,
    "starbase": 3,
}


async def create_player_resources(player: Player, db: AsyncSession) -> PlayerResources:
    """Create and persist starting resources for a player based on their species."""
    species_data = get_species(player.species)
    resources = PlayerResources(
        player_id=player.id,
        money=species_data.starting_money,
        science=species_data.starting_science,
        materials=species_data.starting_materials,
        population_cubes={"orbital": 5, "advanced": 5, "gauss": 5},
        tradespheres=0,
        influence_discs_total=11,
        influence_discs_used=0,
    )
    db.add(resources)
    await db.flush()
    return resources


async def get_player_resources(player_id: int, db: AsyncSession) -> PlayerResources | None:
    """Fetch the PlayerResources record for a given player."""
    result = await db.execute(
        select(PlayerResources).where(PlayerResources.player_id == player_id)
    )
    return result.scalar_one_or_none()


async def use_influence_disc(player_id: int, db: AsyncSession) -> None:
    """Place one influence disc on the board when a player takes an action.

    Raises ValueError if the player has no discs remaining.
    """
    resources = await get_player_resources(player_id, db)
    if resources is None:
        raise ValueError("Player has no resources record")
    remaining = resources.influence_discs_total - resources.influence_discs_used
    if remaining <= 0:
        raise ValueError(
            "No influence discs remaining — all are placed on the board"
        )
    resources.influence_discs_used += 1
    await db.flush()


async def validate_and_deduct_build_cost(
    player_id: int, ship_type: str, db: AsyncSession
) -> None:
    """Validate the player can afford to build the given ship type and deduct materials."""
    ship_key = ship_type.lower()
    cost = BUILD_COSTS.get(ship_key)
    if cost is None:
        raise ValueError(f"Unknown ship type: '{ship_type}'")

    resources = await get_player_resources(player_id, db)
    if resources is None:
        raise ValueError("Player has no resources record")
    if resources.materials < cost:
        raise ValueError(
            f"Insufficient materials to build {ship_type}: "
            f"need {cost}, have {resources.materials}"
        )
    resources.materials -= cost
    await db.flush()


async def validate_and_deduct_research_cost(
    player_id: int, science_cost: int, db: AsyncSession
) -> None:
    """Validate the player has enough science and deduct the research cost."""
    resources = await get_player_resources(player_id, db)
    if resources is None:
        raise ValueError("Player has no resources record")
    if resources.science < science_cost:
        raise ValueError(
            f"Insufficient science: need {science_cost}, have {resources.science}"
        )
    resources.science -= science_cost
    await db.flush()


async def perform_upkeep_for_player(player_id: int, db: AsyncSession) -> dict:
    """Apply upkeep for a single player.

    Steps:
    1. Add income: tradespheres (1 money each) + colony income (Task 11)
    2. Deduct influence costs for colony hexes at 1 money each (Task 11)
    3. Handle bankruptcy: remove colony hexes if player cannot pay
    4. Return action-tile influence discs to player's supply
    """
    resources = await get_player_resources(player_id, db)
    if resources is None:
        return {}

    # Income sources
    money_income = resources.tradespheres  # 1 money per tradesphere
    science_income = 0   # from colony science planets (added in Task 11)
    materials_income = 0  # from colony materials planets (added in Task 11)

    resources.money += money_income
    resources.science += science_income
    resources.materials += materials_income

    # Influence cost: 1 money per colony hex disc.
    # Colony discs will be tracked in Task 11; for now cost is 0.
    colony_disc_count = 0  # TODO Task 11: count colony discs for this player
    influence_cost = colony_disc_count

    bankrupt = False
    discs_removed = 0

    if resources.money >= influence_cost:
        resources.money -= influence_cost
    else:
        # Bankruptcy: pay what we can, remove colony hexes until solvent
        shortage = influence_cost - resources.money
        resources.money = 0
        bankrupt = True
        discs_removed = shortage
        colony_disc_count -= discs_removed

    # Return action-tile discs (free at end of upkeep).
    # Colony discs stay; for now all discs_used are action discs, so reset to colony count.
    resources.influence_discs_used = colony_disc_count  # = 0 while no colonies exist

    await db.flush()
    return {
        "money_gained": money_income,
        "science_gained": science_income,
        "materials_gained": materials_income,
        "influence_cost": influence_cost,
        "bankrupt": bankrupt,
        "discs_removed": discs_removed,
    }


async def apply_upkeep_for_game(player_ids: list[int], db: AsyncSession) -> None:
    """Run upkeep for all players in a game."""
    for player_id in player_ids:
        await perform_upkeep_for_player(player_id, db)
