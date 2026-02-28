"""
Galaxy map generation for Eclipse: Second Dawn.

Uses axial coordinate system (pointy-top hexagons):
  Direction 0: (q+1, r  ) - East
  Direction 1: (q+1, r-1) - North-East
  Direction 2: (q,   r-1) - North-West
  Direction 3: (q-1, r  ) - West
  Direction 4: (q-1, r+1) - South-West
  Direction 5: (q,   r+1) - South-East

Opposite of direction d is (d + 3) % 6.
"""

import random

from sqlalchemy.ext.asyncio import AsyncSession

from app.data.system_tiles import (
    ALL_TILES,
    GALACTIC_CENTER,
    HOMEWORLD_TILES,
    INNER_RING_TILES,
    OUTER_RING_TILES,
    STARTING_SECTOR_TILES,
    SystemTile,
)
from app.models.hex_tile import HexTile, TileType
from app.models.player import Player
from app.models.system import System

# Axial direction vectors for pointy-top hexagons
DIRECTIONS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]

# Which spoke indices each player count uses (evenly spaced around the 6 possible spokes)
_SPOKE_INDICES_BY_PLAYER_COUNT: dict[int, list[int]] = {
    2: [0, 3],
    3: [0, 2, 4],
    4: [0, 1, 3, 4],
    5: [0, 1, 2, 3, 4],
    6: [0, 1, 2, 3, 4, 5],
}


def hex_ring(center_q: int, center_r: int, radius: int) -> list[tuple[int, int]]:
    """Return all axial coordinates on ring `radius` around (center_q, center_r).

    Uses the standard algorithm: start at center + radius*dir[4], then walk
    in each of the 6 primary directions for `radius` steps.
    """
    if radius == 0:
        return [(center_q, center_r)]
    results: list[tuple[int, int]] = []
    dq, dr = DIRECTIONS[4]
    q = center_q + dq * radius
    r = center_r + dr * radius
    for i in range(6):
        for _ in range(radius):
            results.append((q, r))
            dq2, dr2 = DIRECTIONS[i]
            q += dq2
            r += dr2
    return results


def effective_wormholes(template: SystemTile, rotation: int) -> set[int]:
    """Return the set of wormhole directions after applying `rotation` steps."""
    return {(w + rotation) % 6 for w in template.wormholes}


def tiles_share_wormhole(
    template_a: SystemTile,
    rotation_a: int,
    template_b: SystemTile,
    rotation_b: int,
    direction_a_to_b: int,
) -> bool:
    """Return True if tile A (in direction `direction_a_to_b`) and tile B have aligned wormholes.

    Both tiles must have wormholes facing each other: A must have a wormhole in
    direction_a_to_b and B must have a wormhole in (direction_a_to_b + 3) % 6.
    """
    dir_b_to_a = (direction_a_to_b + 3) % 6
    wh_a = effective_wormholes(template_a, rotation_a)
    wh_b = effective_wormholes(template_b, rotation_b)
    return direction_a_to_b in wh_a and dir_b_to_a in wh_b


def _spoke_position(spoke_idx: int, distance: int) -> tuple[int, int]:
    """Return axial position at `distance` steps from origin in spoke direction `spoke_idx`."""
    dq, dr = DIRECTIONS[spoke_idx]
    return dq * distance, dr * distance


def _make_system(tile: HexTile, template: SystemTile, rotation: int) -> System:
    """Create a System record for an explored tile."""
    eff_wh = sorted(effective_wormholes(template, rotation))
    return System(
        hex_tile_id=tile.id,
        name=template.name,
        planets=[{"type": p.type, "advanced": p.advanced} for p in template.planets],
        wormholes=eff_wh,
        ancient_ships_count=template.ancient_ships_count,
    )


async def generate_map(db: AsyncSession, game_id: int, players: list[Player]) -> list[HexTile]:
    """Generate and persist a galaxy map for `game_id`.

    Layout:
    - (0,0): Galactic Center (pre-explored)
    - Ring 1 (distance 1 from center): 6 shuffled inner tiles (unexplored)
    - Ring 2 (distance 2): starting sectors (pre-explored, one per player) + shuffled outer tiles
    - Ring 3 (distance 3): homeworld tiles (pre-explored, one per player) +
      extra outer tiles for 5-6 player games
    """
    n_players = len(players)
    if n_players not in _SPOKE_INDICES_BY_PLAYER_COUNT:
        raise ValueError(f"Unsupported player count: {n_players}")

    spoke_indices = _SPOKE_INDICES_BY_PLAYER_COUNT[n_players]
    placed: dict[tuple[int, int], HexTile] = {}

    # ---- Galactic Center ----
    gc_tile = HexTile(
        game_id=game_id,
        q=0,
        r=0,
        tile_type=TileType.galactic_center,
        tile_template_id=GALACTIC_CENTER.tile_id,
        rotation=0,
        is_explored=True,
        owner_player_id=None,
    )
    db.add(gc_tile)
    placed[(0, 0)] = gc_tile
    await db.flush()

    gc_system = _make_system(gc_tile, GALACTIC_CENTER, 0)
    db.add(gc_system)

    # ---- Homeworld and starting sector tiles (one per player) ----
    sorted_players = sorted(players, key=lambda p: p.turn_order if p.turn_order is not None else 0)
    player_tiles: list[HexTile] = []

    for turn_idx, player in enumerate(sorted_players):
        spoke_idx = spoke_indices[turn_idx]
        species_key = player.species.value  # e.g. "human"

        hw_template = HOMEWORLD_TILES[species_key]
        ss_template = STARTING_SECTOR_TILES[species_key]

        # Homeworld wormhole default is direction 3 (W). For spoke `spoke_idx`,
        # the inward direction is (spoke_idx + 3) % 6. Rotating by spoke_idx shifts 3 → spoke_idx+3 ≡ inward.
        hw_rotation = spoke_idx
        ss_rotation = spoke_idx  # starting sector wormholes [0,3] become [spoke, spoke+3 mod 6]

        hw_q, hw_r = _spoke_position(spoke_idx, 3)
        ss_q, ss_r = _spoke_position(spoke_idx, 2)

        hw_tile = HexTile(
            game_id=game_id,
            q=hw_q,
            r=hw_r,
            tile_type=TileType.homeworld,
            tile_template_id=hw_template.tile_id,
            rotation=hw_rotation,
            is_explored=True,
            owner_player_id=player.id,
        )
        db.add(hw_tile)
        placed[(hw_q, hw_r)] = hw_tile
        player_tiles.append(hw_tile)

        ss_tile = HexTile(
            game_id=game_id,
            q=ss_q,
            r=ss_r,
            tile_type=TileType.starting_sector,
            tile_template_id=ss_template.tile_id,
            rotation=ss_rotation,
            is_explored=True,
            owner_player_id=player.id,
        )
        db.add(ss_tile)
        placed[(ss_q, ss_r)] = ss_tile
        player_tiles.append(ss_tile)

    await db.flush()

    # Create System records for all pre-explored player tiles
    for tile in player_tiles:
        template = ALL_TILES[tile.tile_template_id]
        db.add(_make_system(tile, template, tile.rotation))

    # ---- Ring 1: inner tiles (all 6 positions, never overlap with player sectors) ----
    ring1_positions = hex_ring(0, 0, 1)
    inner_available = [pos for pos in ring1_positions if pos not in placed]

    inner_pool = list(INNER_RING_TILES)
    random.shuffle(inner_pool)

    for i, pos in enumerate(inner_available):
        template = inner_pool[i % len(inner_pool)]
        tile = HexTile(
            game_id=game_id,
            q=pos[0],
            r=pos[1],
            tile_type=TileType.inner,
            tile_template_id=template.tile_id,
            rotation=0,
            is_explored=False,
        )
        db.add(tile)
        placed[pos] = tile

    # ---- Ring 2: remaining positions get outer tiles ----
    ring2_positions = hex_ring(0, 0, 2)
    ring2_available = [pos for pos in ring2_positions if pos not in placed]

    outer_pool = list(OUTER_RING_TILES)
    random.shuffle(outer_pool)
    outer_idx = 0

    for pos in ring2_available:
        template = outer_pool[outer_idx % len(outer_pool)]
        outer_idx += 1
        tile = HexTile(
            game_id=game_id,
            q=pos[0],
            r=pos[1],
            tile_type=TileType.outer,
            tile_template_id=template.tile_id,
            rotation=0,
            is_explored=False,
        )
        db.add(tile)
        placed[pos] = tile

    # ---- Ring 3: extra outer tiles for 5-6 player games ----
    if n_players >= 5:
        ring3_positions = hex_ring(0, 0, 3)
        ring3_available = [pos for pos in ring3_positions if pos not in placed]

        for pos in ring3_available:
            template = outer_pool[outer_idx % len(outer_pool)]
            outer_idx += 1
            tile = HexTile(
                game_id=game_id,
                q=pos[0],
                r=pos[1],
                tile_type=TileType.outer,
                tile_template_id=template.tile_id,
                rotation=0,
                is_explored=False,
            )
            db.add(tile)
            placed[pos] = tile

    await db.flush()
    return list(placed.values())


async def get_map_tiles(db: AsyncSession, game_id: int) -> list[HexTile]:
    """Fetch all HexTile records for a game."""
    from sqlalchemy import select

    result = await db.execute(select(HexTile).where(HexTile.game_id == game_id))
    return list(result.scalars().all())


async def get_system_for_tile(db: AsyncSession, hex_tile_id: int) -> System | None:
    """Fetch the System record for a given hex tile."""
    from sqlalchemy import select

    result = await db.execute(select(System).where(System.hex_tile_id == hex_tile_id))
    return result.scalar_one_or_none()
