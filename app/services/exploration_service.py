"""Exploration service for Eclipse: Second Dawn.

Handles the EXPLORE action: revealing unexplored sectors, placing ancient ships,
drawing and applying discovery tiles.

Also handles the INFLUENCE action: placing an influence disc on an explored,
unowned sector that the player occupies with a ship.

Discovery deck:
- Initialized at game start (shuffled list of all templates).
- On EXPLORE, the lowest draw_order undrawn tile is drawn.
- The tile's effect is immediately applied to the player's resources/VP.
"""

import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.discovery_tiles import DISCOVERY_TILE_TEMPLATES, get_discovery_tile
from app.data.system_tiles import ALL_TILES
from app.models.discovery_tile import DiscoveryTile
from app.models.hex_tile import HexTile
from app.models.player import Player
from app.models.ship import Ship
from app.models.system import System
from app.services.movement_service import are_hexes_wormhole_connected
from app.services.resource_service import get_player_resources, use_influence_disc


# ---------------------------------------------------------------------------
# Discovery deck initialization
# ---------------------------------------------------------------------------

async def initialize_discovery_deck(db: AsyncSession, game_id: int) -> list[DiscoveryTile]:
    """Create a shuffled discovery deck for a game.

    One DiscoveryTile row per template, with a random draw_order assigned.
    Called from game_service.start_game.
    """
    templates = list(DISCOVERY_TILE_TEMPLATES)
    random.shuffle(templates)

    tiles: list[DiscoveryTile] = []
    for order, template in enumerate(templates):
        tile = DiscoveryTile(
            game_id=game_id,
            discovery_template_id=template.discovery_id,
            draw_order=order,
            is_drawn=False,
        )
        db.add(tile)
        tiles.append(tile)

    await db.flush()
    return tiles


# ---------------------------------------------------------------------------
# Drawing a discovery tile
# ---------------------------------------------------------------------------

async def draw_discovery_tile(
    db: AsyncSession,
    game_id: int,
    player_id: int,
    hex_tile_id: int,
) -> DiscoveryTile | None:
    """Draw the next discovery tile from the deck and record the draw.

    Returns the DiscoveryTile row (with template ID filled in), or None if the
    deck is exhausted.
    """
    result = await db.execute(
        select(DiscoveryTile)
        .where(
            DiscoveryTile.game_id == game_id,
            DiscoveryTile.is_drawn == False,  # noqa: E712
        )
        .order_by(DiscoveryTile.draw_order)
        .limit(1)
    )
    tile = result.scalar_one_or_none()
    if tile is None:
        return None  # deck exhausted

    tile.is_drawn = True
    tile.drawn_by_player_id = player_id
    tile.hex_tile_id = hex_tile_id
    await db.flush()
    return tile


# ---------------------------------------------------------------------------
# Applying discovery effects
# ---------------------------------------------------------------------------

async def apply_discovery_effect(
    db: AsyncSession,
    player_id: int,
    discovery_tile: DiscoveryTile,
    game_id: int,
) -> dict:
    """Apply the effect of a drawn discovery tile to the player.

    Returns a dict describing what happened.
    """
    template = get_discovery_tile(discovery_tile.discovery_template_id)
    resources = await get_player_resources(player_id, db)

    effect_summary: dict = {
        "discovery_id": template.discovery_id,
        "name": template.name,
        "effect_type": template.effect_type,
        "effect_value": template.effect_value,
    }

    if template.effect_type == "money" and resources is not None:
        resources.money += template.effect_value
        await db.flush()

    elif template.effect_type == "science" and resources is not None:
        resources.science += template.effect_value
        await db.flush()

    elif template.effect_type == "materials" and resources is not None:
        resources.materials += template.effect_value
        await db.flush()

    elif template.effect_type == "orbital":
        # Award VP immediately
        result = await db.execute(
            select(Player).where(Player.id == player_id)
        )
        player = result.scalar_one_or_none()
        if player is not None:
            player.vp_count += template.effect_value
            await db.flush()

    elif template.effect_type == "ancient_cruiser":
        # Place an ancient cruiser on the explored hex, now owned by the player.
        # (The "ancient cruiser" discovery gives you a derelict ship to use.)
        # We place it as a non-ancient ship type "cruiser" owned by the player,
        # since the player has reprogrammed/claimed it.
        hex_tile_id = discovery_tile.hex_tile_id
        if hex_tile_id is not None:
            cruiser = Ship(
                game_id=game_id,
                player_id=player_id,
                ship_type="cruiser",
                hex_tile_id=hex_tile_id,
                hp_remaining=1,
                is_ancient=False,
            )
            db.add(cruiser)
            await db.flush()
            effect_summary["ship_placed"] = True

    # "empty" — no effect

    return effect_summary


# ---------------------------------------------------------------------------
# Revealing an unexplored hex tile
# ---------------------------------------------------------------------------

async def _reveal_hex(
    db: AsyncSession, hex_tile: HexTile
) -> System:
    """Create a System record for a newly-explored hex tile.

    The template data + rotation determine the planets, wormholes, and
    ancient ship count.  Ancient ships are placed as Ship records with
    player_id=None, is_ancient=True.
    """
    template_id = hex_tile.tile_template_id
    if template_id is None or template_id not in ALL_TILES:
        # Fallback: empty system
        system = System(
            hex_tile_id=hex_tile.id,
            name="Unknown System",
            planets=[],
            wormholes=[],
            ancient_ships_count=0,
        )
        db.add(system)
        await db.flush()
        return system

    template = ALL_TILES[template_id]
    rotation = hex_tile.rotation or 0
    effective_wh = sorted(
        {(w + rotation) % 6 for w in template.wormholes}
    )

    system = System(
        hex_tile_id=hex_tile.id,
        name=template.name,
        planets=[{"type": p.type, "advanced": p.advanced} for p in template.planets],
        wormholes=effective_wh,
        ancient_ships_count=template.ancient_ships_count,
    )
    db.add(system)
    await db.flush()
    return system


async def _place_ancient_ships(
    db: AsyncSession, game_id: int, hex_tile_id: int, count: int
) -> list[Ship]:
    """Place ancient (NPC) ships on a newly-explored hex."""
    ships: list[Ship] = []
    for _ in range(count):
        ship = Ship(
            game_id=game_id,
            player_id=None,
            ship_type="cruiser",   # ancient ships use cruiser stats
            hex_tile_id=hex_tile_id,
            hp_remaining=1,
            is_ancient=True,
        )
        db.add(ship)
        ships.append(ship)
    await db.flush()
    return ships


# ---------------------------------------------------------------------------
# EXPLORE action
# ---------------------------------------------------------------------------

async def execute_explore(
    db: AsyncSession,
    game_id: int,
    player_id: int,
    ship_id: int,
    target_hex_id: int,
) -> dict:
    """Execute an EXPLORE action.

    The ship at its current location moves into an adjacent unexplored hex,
    revealing it.  The player must have enough influence discs to claim the
    new system (one additional disc beyond the action disc already used by
    the turn engine).

    Returns a summary dict of what happened.
    Raises ValueError on any validation failure.
    """
    # --- fetch ship ---
    result = await db.execute(select(Ship).where(Ship.id == ship_id))
    ship = result.scalar_one_or_none()
    if ship is None:
        raise ValueError(f"Ship {ship_id} not found")
    if ship.game_id != game_id:
        raise ValueError(f"Ship {ship_id} does not belong to game {game_id}")
    if ship.player_id != player_id:
        raise ValueError("You do not own this ship")
    if ship.hex_tile_id is None:
        raise ValueError("Ship has no current position on the map")

    # --- fetch source hex ---
    result = await db.execute(select(HexTile).where(HexTile.id == ship.hex_tile_id))
    source_hex = result.scalar_one_or_none()
    if source_hex is None or not source_hex.is_explored:
        raise ValueError("Ship must be on an explored hex to explore")

    # --- fetch target hex ---
    result = await db.execute(select(HexTile).where(HexTile.id == target_hex_id))
    target_hex = result.scalar_one_or_none()
    if target_hex is None:
        raise ValueError(f"Target hex {target_hex_id} not found")
    if target_hex.game_id != game_id:
        raise ValueError(f"Target hex {target_hex_id} does not belong to this game")
    if target_hex.is_explored:
        raise ValueError(
            f"Hex {target_hex_id} is already explored — use MOVE to enter it"
        )

    # --- validate adjacency and wormhole connection ---
    from app.services.movement_service import direction_between
    direction = direction_between(
        source_hex.q, source_hex.r, target_hex.q, target_hex.r
    )
    if direction is None:
        raise ValueError(
            f"Target hex ({target_hex.q},{target_hex.r}) is not adjacent to "
            f"ship's current hex ({source_hex.q},{source_hex.r})"
        )

    connected = await are_hexes_wormhole_connected(db, source_hex, target_hex)
    if not connected:
        raise ValueError(
            f"No wormhole connection from ({source_hex.q},{source_hex.r}) "
            f"to ({target_hex.q},{target_hex.r})"
        )

    # --- validate influence discs (need 1 more after action disc already used) ---
    resources = await get_player_resources(player_id, db)
    if resources is None:
        raise ValueError("Player has no resources record")
    remaining = resources.influence_discs_total - resources.influence_discs_used
    if remaining < 1:
        raise ValueError(
            "No influence discs remaining to claim the explored system — "
            "cannot explore (would have to retreat)"
        )

    # --- reveal the hex ---
    target_hex.is_explored = True
    system = await _reveal_hex(db, target_hex)

    # --- place ancient ships ---
    ancient_count = system.ancient_ships_count
    ancient_ships = []
    if ancient_count > 0:
        ancient_ships = await _place_ancient_ships(
            db, game_id, target_hex.id, ancient_count
        )

    # --- claim the hex (place influence disc) ---
    target_hex.owner_player_id = player_id
    await use_influence_disc(player_id, db)

    # --- move ship to new hex ---
    ship.hex_tile_id = target_hex.id

    # --- draw and apply discovery tile ---
    discovery_summary: dict | None = None
    template = ALL_TILES.get(target_hex.tile_template_id or "")
    has_discovery = template.has_discovery if template else False

    if has_discovery:
        disc_tile = await draw_discovery_tile(db, game_id, player_id, target_hex.id)
        if disc_tile is not None:
            discovery_summary = await apply_discovery_effect(
                db, player_id, disc_tile, game_id
            )

    await db.flush()

    return {
        "hex_revealed": target_hex_id,
        "system_name": system.name,
        "planets": system.planets,
        "wormholes": system.wormholes,
        "ancient_ships_placed": len(ancient_ships),
        "discovery": discovery_summary,
    }


# ---------------------------------------------------------------------------
# INFLUENCE action
# ---------------------------------------------------------------------------

async def execute_influence(
    db: AsyncSession,
    game_id: int,
    player_id: int,
    hex_tile_id: int,
) -> dict:
    """Execute an INFLUENCE action: claim an explored, unowned hex.

    The player must have at least one ship on the target hex.
    The influence disc for the action tile is already consumed by the turn
    engine; no additional disc is needed here (the action tile disc *is* the
    influence being placed on the system in the abstract — Eclipse's rule is
    that placing a disc on the action tile == using an influence action).

    Returns a summary dict.
    Raises ValueError on any validation failure.
    """
    result = await db.execute(select(HexTile).where(HexTile.id == hex_tile_id))
    hex_tile = result.scalar_one_or_none()
    if hex_tile is None:
        raise ValueError(f"Hex tile {hex_tile_id} not found")
    if hex_tile.game_id != game_id:
        raise ValueError(f"Hex tile {hex_tile_id} does not belong to this game")
    if not hex_tile.is_explored:
        raise ValueError(f"Hex {hex_tile_id} has not been explored yet")
    if hex_tile.owner_player_id is not None:
        raise ValueError(
            f"Hex {hex_tile_id} is already claimed by player {hex_tile.owner_player_id}"
        )

    # Player must have at least one ship on the hex
    result = await db.execute(
        select(Ship).where(
            Ship.game_id == game_id,
            Ship.player_id == player_id,
            Ship.hex_tile_id == hex_tile_id,
        )
    )
    ships_on_hex = list(result.scalars().all())
    if not ships_on_hex:
        raise ValueError(
            f"Player has no ships on hex {hex_tile_id} — "
            "must have a ship present to place influence"
        )

    hex_tile.owner_player_id = player_id
    await db.flush()

    return {"hex_claimed": hex_tile_id, "owner_player_id": player_id}


# ---------------------------------------------------------------------------
# Map query
# ---------------------------------------------------------------------------

async def get_full_map(db: AsyncSession, game_id: int) -> list[dict]:
    """Return a full map snapshot for a game.

    Each entry contains:
    - tile info (id, q, r, tile_type, is_explored, owner_player_id)
    - system info if explored (name, planets, wormholes, ancient_ships_count)
    - ships present on the tile
    """
    # Fetch all tiles
    tile_result = await db.execute(
        select(HexTile).where(HexTile.game_id == game_id)
    )
    tiles = list(tile_result.scalars().all())

    # Fetch all systems for this game (join via hex_tile)
    tile_ids = [t.id for t in tiles]
    system_result = await db.execute(
        select(System).where(System.hex_tile_id.in_(tile_ids))
    )
    systems_by_tile: dict[int, System] = {
        s.hex_tile_id: s for s in system_result.scalars().all()
    }

    # Fetch all ships for this game
    ship_result = await db.execute(
        select(Ship).where(Ship.game_id == game_id)
    )
    ships_by_tile: dict[int, list[Ship]] = {}
    for ship in ship_result.scalars().all():
        if ship.hex_tile_id is not None:
            ships_by_tile.setdefault(ship.hex_tile_id, []).append(ship)

    map_data: list[dict] = []
    for tile in tiles:
        entry: dict = {
            "id": tile.id,
            "q": tile.q,
            "r": tile.r,
            "tile_type": tile.tile_type.value,
            "is_explored": tile.is_explored,
            "owner_player_id": tile.owner_player_id,
            "system": None,
            "ships": [],
        }
        sys = systems_by_tile.get(tile.id)
        if sys is not None:
            entry["system"] = {
                "id": sys.id,
                "name": sys.name,
                "planets": sys.planets or [],
                "wormholes": sys.wormholes or [],
                "ancient_ships_count": sys.ancient_ships_count,
            }
        ships = ships_by_tile.get(tile.id, [])
        entry["ships"] = [
            {
                "id": s.id,
                "ship_type": s.ship_type,
                "player_id": s.player_id,
                "hp_remaining": s.hp_remaining,
                "is_ancient": s.is_ancient,
            }
            for s in ships
        ]
        map_data.append(entry)

    return map_data
