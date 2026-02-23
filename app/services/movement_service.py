"""Movement service for Eclipse: Second Dawn.

Handles the MOVE action: validating ship movement paths and updating ship
positions in the database.

Movement rules:
- Only moveable ships (not starbases) can move.
- A ship's movement range equals the sum of all Drive component movement
  values in its blueprint.
- The movement path is a list of hex tile IDs (not including the starting
  hex).  Each step must be through a wormhole connection.
- Two adjacent hexes are wormhole-connected if tile A has a wormhole facing
  tile B AND tile B has a wormhole facing tile A.
- All intermediate hexes in the path (all but the last) must already be
  explored (ships cannot pass through unexplored space).
- The destination hex must be explored (use EXPLORE for unexplored hexes).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.ship_parts import ComponentCategory, get_component, get_ship_type
from app.data.system_tiles import ALL_TILES
from app.models.hex_tile import HexTile
from app.models.ship import Ship
from app.models.ship_blueprint import ShipBlueprint
from app.models.system import System

# Axial direction vectors (pointy-top hexes) — same as map_generator.py
DIRECTIONS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


def direction_between(q1: int, r1: int, q2: int, r2: int) -> int | None:
    """Return the direction index (0-5) from (q1,r1) to (q2,r2), or None if not adjacent."""
    dq, dr = q2 - q1, r2 - r1
    for i, (ddq, ddr) in enumerate(DIRECTIONS):
        if (ddq, ddr) == (dq, dr):
            return i
    return None


def effective_wormholes_for_hex(hex_tile: HexTile, system: System | None) -> set[int]:
    """Return the set of active wormhole directions for a hex tile.

    For explored tiles, use the System.wormholes list (already rotated).
    For unexplored tiles (no System yet), compute from template + rotation.
    """
    if system is not None and system.wormholes is not None:
        return set(system.wormholes)
    # Unexplored tile — derive from static template data
    if hex_tile.tile_template_id and hex_tile.tile_template_id in ALL_TILES:
        template = ALL_TILES[hex_tile.tile_template_id]
        rotation = hex_tile.rotation or 0
        return {(w + rotation) % 6 for w in template.wormholes}
    return set()


async def _get_hex_by_id(db: AsyncSession, hex_tile_id: int) -> HexTile | None:
    result = await db.execute(select(HexTile).where(HexTile.id == hex_tile_id))
    return result.scalar_one_or_none()


async def _get_system_for_hex(db: AsyncSession, hex_tile_id: int) -> System | None:
    result = await db.execute(select(System).where(System.hex_tile_id == hex_tile_id))
    return result.scalar_one_or_none()


async def _get_hex_at(
    db: AsyncSession, game_id: int, q: int, r: int
) -> HexTile | None:
    result = await db.execute(
        select(HexTile).where(
            HexTile.game_id == game_id,
            HexTile.q == q,
            HexTile.r == r,
        )
    )
    return result.scalar_one_or_none()


async def are_hexes_wormhole_connected(
    db: AsyncSession,
    hex_a: HexTile,
    hex_b: HexTile,
) -> bool:
    """Return True if hex_a and hex_b are adjacent and share a wormhole connection."""
    direction = direction_between(hex_a.q, hex_a.r, hex_b.q, hex_b.r)
    if direction is None:
        return False  # not adjacent

    sys_a = await _get_system_for_hex(db, hex_a.id)
    sys_b = await _get_system_for_hex(db, hex_b.id)

    wh_a = effective_wormholes_for_hex(hex_a, sys_a)
    wh_b = effective_wormholes_for_hex(hex_b, sys_b)

    opposite = (direction + 3) % 6
    return direction in wh_a and opposite in wh_b


async def get_ship_movement_range(
    player_id: int, ship_type: str, db: AsyncSession
) -> int:
    """Return the total movement range of a player's ship type from its blueprint."""
    result = await db.execute(
        select(ShipBlueprint).where(
            ShipBlueprint.player_id == player_id,
            ShipBlueprint.ship_type == ship_type.lower(),
        )
    )
    bp = result.scalar_one_or_none()
    if bp is None:
        # Fallback to static default (electron_drive gives 1)
        return 1

    total = 0
    for component_id in (bp.slots or []):
        if component_id is None:
            continue
        try:
            comp = get_component(component_id)
            if comp.category == ComponentCategory.drive:
                total += comp.movement
        except KeyError:
            pass
    return total if total > 0 else 1  # minimum 1


async def validate_and_execute_move(
    db: AsyncSession,
    game_id: int,
    player_id: int,
    ship_id: int,
    path_hex_ids: list[int],
) -> Ship:
    """Validate and execute a MOVE action.

    Args:
        db:            Async database session.
        game_id:       The game being played.
        player_id:     The player performing the move.
        ship_id:       The ship to move.
        path_hex_ids:  Ordered list of hex tile IDs to move through.
                       The last element is the final destination.
                       The current hex is NOT included.

    Returns the updated Ship record.
    Raises ValueError on any validation failure.
    """
    if not path_hex_ids:
        raise ValueError("MOVE path must contain at least one destination hex")

    # Fetch the ship
    result = await db.execute(select(Ship).where(Ship.id == ship_id))
    ship = result.scalar_one_or_none()
    if ship is None:
        raise ValueError(f"Ship {ship_id} not found")
    if ship.game_id != game_id:
        raise ValueError(f"Ship {ship_id} does not belong to game {game_id}")
    if ship.player_id != player_id:
        raise ValueError("You do not own this ship")

    # Check the ship type can move
    try:
        st = get_ship_type(ship.ship_type)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc
    if not st.can_move:
        raise ValueError(f"{st.name} is immobile and cannot move")

    # Check movement range
    move_range = await get_ship_movement_range(player_id, ship.ship_type, db)
    if len(path_hex_ids) > move_range:
        raise ValueError(
            f"Path length {len(path_hex_ids)} exceeds ship movement range {move_range}"
        )

    if ship.hex_tile_id is None:
        raise ValueError("Ship has no current position on the map")

    # Build and validate the full path (starting hex + path hexes)
    current_hex = await _get_hex_by_id(db, ship.hex_tile_id)
    if current_hex is None:
        raise ValueError("Ship's current hex not found")

    for i, next_hex_id in enumerate(path_hex_ids):
        next_hex = await _get_hex_by_id(db, next_hex_id)
        if next_hex is None:
            raise ValueError(f"Hex tile {next_hex_id} not found")
        if next_hex.game_id != game_id:
            raise ValueError(f"Hex {next_hex_id} does not belong to this game")

        # All hexes must be explored
        if not next_hex.is_explored:
            raise ValueError(
                f"Cannot MOVE into unexplored hex {next_hex_id} — use EXPLORE instead"
            )

        # Each step must be wormhole-connected
        connected = await are_hexes_wormhole_connected(db, current_hex, next_hex)
        if not connected:
            raise ValueError(
                f"No wormhole connection from hex {current_hex.id} "
                f"({current_hex.q},{current_hex.r}) to hex {next_hex_id} "
                f"({next_hex.q},{next_hex.r})"
            )

        current_hex = next_hex

    # Execute the move
    ship.hex_tile_id = path_hex_ids[-1]
    await db.flush()
    return ship


async def get_ship_by_id(db: AsyncSession, ship_id: int) -> Ship | None:
    result = await db.execute(select(Ship).where(Ship.id == ship_id))
    return result.scalar_one_or_none()
