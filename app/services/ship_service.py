"""Ship service — manages ship blueprints, BUILD actions, and UPGRADE actions.

Responsibilities:
  - Initialize default ship blueprints for each player on game start
  - Validate and process UPGRADE actions (modify blueprint component slots)
  - Validate BUILD actions (ship count limits) and place Ship records
  - Expose helpers for querying blueprints and ships
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.ship_parts import (
    ShipType,
    compute_power_balance,
    get_component,
    get_ship_type,
    list_ship_types,
    validate_blueprint_power,
)
from app.models.player import Player, Species
from app.models.ship import Ship
from app.models.ship_blueprint import ShipBlueprint


# ---------------------------------------------------------------------------
# Species-specific default blueprint overrides
# ---------------------------------------------------------------------------
# Most species use the standard default_slots from ShipType.  A few species
# have slightly different starting blueprints due to special abilities.

def _get_default_slots(ship_type: ShipType, species: Species) -> list[str | None]:
    """Return the default blueprint slots for (ship_type, species)."""
    slots = list(ship_type.default_slots)  # copy

    if species == Species.orion_hegemony and ship_type.ship_type_id == "interceptor":
        # Orion Hegemony Warfleet: Interceptors start with an extra electron_cannon
        # Replace the first None slot with an additional cannon
        for i, slot in enumerate(slots):
            if slot is None:
                slots[i] = "electron_cannon"
                break

    return slots


# ---------------------------------------------------------------------------
# Blueprint initialization
# ---------------------------------------------------------------------------

async def initialize_blueprints(player: Player, db: AsyncSession) -> list[ShipBlueprint]:
    """Create default ShipBlueprint rows for all four ship types for the player.

    Called from game_service.start_game for every player when the game launches.
    """
    blueprints: list[ShipBlueprint] = []
    for ship_type in list_ship_types():
        slots = _get_default_slots(ship_type, player.species)
        is_valid = validate_blueprint_power(slots)
        bp = ShipBlueprint(
            player_id=player.id,
            ship_type=ship_type.ship_type_id,
            slots=slots,
            is_valid=is_valid,
        )
        db.add(bp)
        blueprints.append(bp)
    await db.flush()
    return blueprints


# ---------------------------------------------------------------------------
# Blueprint queries
# ---------------------------------------------------------------------------

async def get_blueprints_for_player(
    player_id: int, db: AsyncSession
) -> list[ShipBlueprint]:
    """Return all blueprint records for the given player."""
    result = await db.execute(
        select(ShipBlueprint).where(ShipBlueprint.player_id == player_id)
    )
    return list(result.scalars().all())


async def get_blueprint(
    player_id: int, ship_type: str, db: AsyncSession
) -> ShipBlueprint | None:
    """Return the blueprint for a specific (player, ship_type) pair."""
    result = await db.execute(
        select(ShipBlueprint).where(
            ShipBlueprint.player_id == player_id,
            ShipBlueprint.ship_type == ship_type.lower(),
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# UPGRADE action
# ---------------------------------------------------------------------------

async def apply_upgrade(
    player_id: int,
    ship_type: str,
    new_slots: list[str | None],
    owned_tech_ids: set[str],
    db: AsyncSession,
) -> ShipBlueprint:
    """Validate and apply an UPGRADE action to a ship blueprint.

    Args:
        player_id:      The player performing the upgrade.
        ship_type:      The ship type blueprint to modify ("interceptor", etc.).
        new_slots:      Proposed component slot list (may contain None for empty).
        owned_tech_ids: Set of tech_ids the player currently owns.
        db:             Async database session.

    Returns the updated ShipBlueprint.
    Raises ValueError on any validation failure.
    """
    ship_type = ship_type.lower()
    try:
        st = get_ship_type(ship_type)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc

    # Validate slot count
    if len(new_slots) != st.slot_count:
        raise ValueError(
            f"Blueprint for '{ship_type}' must have exactly {st.slot_count} slots, "
            f"got {len(new_slots)}"
        )

    # Validate each component
    for component_id in new_slots:
        if component_id is None:
            continue
        try:
            comp = get_component(component_id)
        except KeyError as exc:
            raise ValueError(str(exc)) from exc
        if comp.requires_tech and comp.requires_tech not in owned_tech_ids:
            raise ValueError(
                f"Component '{comp.name}' requires technology '{comp.requires_tech}' "
                f"which has not been researched"
            )

    # Validate power balance
    if not validate_blueprint_power(new_slots):
        power = compute_power_balance(new_slots)
        raise ValueError(
            f"Blueprint power balance is {power} (must be >= 0). "
            f"Add more sources or remove power-consuming components."
        )

    # Fetch and update the blueprint
    bp = await get_blueprint(player_id, ship_type, db)
    if bp is None:
        raise ValueError(
            f"Blueprint for '{ship_type}' not found — has the game started?"
        )

    bp.slots = new_slots
    bp.is_valid = True
    await db.flush()
    return bp


# ---------------------------------------------------------------------------
# BUILD action — place Ship records on the homeworld
# ---------------------------------------------------------------------------

async def find_player_homeworld(
    player_id: int, game_id: int, db: AsyncSession
) -> int | None:
    """Return the hex_tile_id of the player's homeworld/starting sector, or None."""
    from app.models.hex_tile import HexTile, TileType
    result = await db.execute(
        select(HexTile).where(
            HexTile.game_id == game_id,
            HexTile.owner_player_id == player_id,
            HexTile.tile_type.in_([TileType.homeworld, TileType.starting_sector]),
        )
    )
    tile = result.scalars().first()
    return tile.id if tile is not None else None


async def build_ship(
    player_id: int,
    game_id: int,
    ship_type: str,
    db: AsyncSession,
) -> Ship:
    """Create a Ship record and place it on the player's homeworld hex.

    This does NOT deduct materials — that is handled in resource_service via
    validate_and_deduct_build_cost before this function is called.

    Raises ValueError if the ship type is unknown or the blueprint is invalid.
    """
    ship_type = ship_type.lower()
    try:
        st = get_ship_type(ship_type)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc

    # Validate that the player's blueprint for this ship type is valid
    bp = await get_blueprint(player_id, ship_type, db)
    if bp is not None and not bp.is_valid:
        raise ValueError(
            f"Blueprint for '{ship_type}' is invalid (power imbalance). "
            f"Upgrade the blueprint before building."
        )

    homeworld_hex_id = await find_player_homeworld(player_id, game_id, db)

    ship = Ship(
        game_id=game_id,
        player_id=player_id,
        ship_type=ship_type,
        hex_tile_id=homeworld_hex_id,
        hp_remaining=st.base_hp,
        is_ancient=False,
    )
    db.add(ship)
    await db.flush()
    return ship


# ---------------------------------------------------------------------------
# Ship queries
# ---------------------------------------------------------------------------

async def get_ships_for_game(game_id: int, db: AsyncSession) -> list[Ship]:
    """Return all ships in the game."""
    result = await db.execute(
        select(Ship).where(Ship.game_id == game_id)
    )
    return list(result.scalars().all())


async def get_ships_for_player(player_id: int, game_id: int, db: AsyncSession) -> list[Ship]:
    """Return all ships belonging to a player in a game."""
    result = await db.execute(
        select(Ship).where(Ship.game_id == game_id, Ship.player_id == player_id)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Starting ship placement
# ---------------------------------------------------------------------------

async def place_starting_ships(player: Player, game_id: int, db: AsyncSession) -> None:
    """Place the species' starting ships on the homeworld hex.

    Called from game_service.start_game for every player.
    """
    from app.data.species import get_species
    species_data = get_species(player.species)
    homeworld_hex_id = await find_player_homeworld(player.id, game_id, db)

    for ship_type_str, count in species_data.starting_ships.items():
        try:
            st = get_ship_type(ship_type_str)
        except KeyError:
            continue
        for _ in range(count):
            ship = Ship(
                game_id=game_id,
                player_id=player.id,
                ship_type=st.ship_type_id,
                hex_tile_id=homeworld_hex_id,
                hp_remaining=st.base_hp,
                is_ancient=False,
            )
            db.add(ship)
    await db.flush()
