"""Research service — validates and processes RESEARCH actions.

Responsibilities:
  - Calculate the effective science cost of a technology after category discounts
  - Validate prerequisites, duplicate acquisition, and science availability
  - Record the acquisition in player_technologies
  - Apply immediate tech effects (income bonuses, stat bonuses) to player state
  - Expose helpers used by the turn engine and the research router
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.technologies import (
    TechCategory,
    Technology,
    get_technology,
    list_technologies_by_category,
)
from app.models.player_resources import PlayerResources
from app.models.player_technology import PlayerTechnology
from app.services.resource_service import get_player_resources


async def get_player_technologies(
    player_id: int, db: AsyncSession
) -> list[PlayerTechnology]:
    """Return all technology records acquired by a player."""
    result = await db.execute(
        select(PlayerTechnology)
        .where(PlayerTechnology.player_id == player_id)
        .order_by(PlayerTechnology.acquired_at)
    )
    return list(result.scalars().all())


async def get_player_tech_ids(player_id: int, db: AsyncSession) -> set[str]:
    """Return the set of tech_ids the player currently owns."""
    techs = await get_player_technologies(player_id, db)
    return {t.tech_id for t in techs}


async def count_techs_in_category(
    player_id: int, category: TechCategory, db: AsyncSession
) -> int:
    """Return how many technologies the player owns in the given category."""
    owned_ids = await get_player_tech_ids(player_id, db)
    category_techs = list_technologies_by_category(category)
    return sum(1 for t in category_techs if t.tech_id in owned_ids)


def calculate_effective_cost(tech: Technology, owned_count_in_category: int) -> int:
    """Return the effective science cost after same-category discount.

    Each technology already owned in the same category reduces the cost by 1,
    down to a minimum of 0.
    """
    discounted = tech.base_cost - owned_count_in_category
    return max(0, discounted)


async def validate_research(
    player_id: int,
    tech_id: str,
    db: AsyncSession,
) -> tuple[Technology, int]:
    """Validate that a player can research the given technology.

    Returns (technology, effective_cost) on success.
    Raises ValueError with a descriptive message on failure.
    """
    # Resolve the technology definition
    try:
        tech = get_technology(tech_id)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc

    # Ancient techs and other non-researchable techs are discovery-only
    if not tech.can_research:
        raise ValueError(
            f"'{tech.name}' cannot be researched — it is obtained only through discovery tiles"
        )

    owned_ids = await get_player_tech_ids(player_id, db)

    # Check duplicate ownership
    if tech_id in owned_ids:
        raise ValueError(f"Player already owns technology '{tech.name}'")

    # Check prerequisites
    for prereq_id in tech.prerequisites:
        if prereq_id not in owned_ids:
            try:
                prereq = get_technology(prereq_id)
                prereq_name = prereq.name
            except KeyError:
                prereq_name = prereq_id
            raise ValueError(
                f"Missing prerequisite '{prereq_name}' for technology '{tech.name}'"
            )

    # Calculate discounted cost
    owned_count = sum(1 for t_id in owned_ids if get_technology(t_id).category == tech.category)
    effective_cost = calculate_effective_cost(tech, owned_count)

    return tech, effective_cost


async def apply_research(
    player_id: int,
    tech_id: str,
    acquired_round: int,
    db: AsyncSession,
) -> PlayerTechnology:
    """Validate, deduct science cost, record acquisition, and apply tech effects.

    The caller is responsible for verifying it is the player's turn and that
    the RESEARCH action is legal in the current game phase.

    Returns the new PlayerTechnology record.
    """
    tech, effective_cost = await validate_research(player_id, tech_id, db)

    # Deduct science cost
    resources: PlayerResources | None = await get_player_resources(player_id, db)
    if resources is None:
        raise ValueError("Player has no resources record")
    if resources.science < effective_cost:
        raise ValueError(
            f"Insufficient science to research '{tech.name}': "
            f"need {effective_cost}, have {resources.science}"
        )
    resources.science -= effective_cost
    await db.flush()

    # Record the acquisition
    record = PlayerTechnology(
        player_id=player_id,
        tech_id=tech_id,
        acquired_round=acquired_round,
    )
    db.add(record)
    await db.flush()

    # Apply immediate tech effects
    await _apply_tech_effects(tech, resources, db)

    return record


async def _apply_tech_effects(
    tech: Technology,
    resources: PlayerResources,
    db: AsyncSession,
) -> None:
    """Apply effects that can be resolved immediately on acquisition.

    Effects that depend on game state not yet available (e.g. colony counts
    for income bonuses, ship blueprints) are recorded implicitly via the
    PlayerTechnology row and evaluated at the appropriate time.
    """
    for effect in tech.effects:
        if effect.effect_type == "income_bonus":
            params = effect.params
            # Flat bonuses (both ongoing and one-time) are applied immediately.
            # Per-planet income bonuses are applied during upkeep (Task 11+);
            # the tech record is the source of truth — no immediate effect here.
            if "flat" in params:
                resource_name = params.get("resource", "")
                flat_amount = params.get("flat", 0)
                if resource_name == "science":
                    resources.science += flat_amount
                elif resource_name == "money":
                    resources.money += flat_amount
                elif resource_name == "materials":
                    resources.materials += flat_amount
    await db.flush()


async def grant_technology(
    player_id: int,
    tech_id: str,
    acquired_round: int,
    db: AsyncSession,
) -> PlayerTechnology:
    """Grant a technology to a player without spending science.

    Used for discovery tiles and species special abilities.
    Validates the tech exists and the player doesn't already own it.
    """
    try:
        tech = get_technology(tech_id)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc

    owned_ids = await get_player_tech_ids(player_id, db)
    if tech_id in owned_ids:
        raise ValueError(f"Player already owns technology '{tech.name}'")

    record = PlayerTechnology(
        player_id=player_id,
        tech_id=tech_id,
        acquired_round=acquired_round,
    )
    db.add(record)

    resources: PlayerResources | None = await get_player_resources(player_id, db)
    if resources is not None:
        await _apply_tech_effects(tech, resources, db)
    else:
        await db.flush()

    return record
