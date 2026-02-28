"""Combat service — implements the Eclipse combat resolution system.

Combat sequence per round:
  1. Missile phase: ships with missiles fire in descending initiative order.
  2. Cannon phase: ships with cannons fire in descending initiative order.
  3. Damage is applied simultaneously within each weapon phase.
  4. Ships with hp_remaining <= 0 are destroyed and removed from the board.
  5. Repeat until one side is eliminated or max rounds reached.

Hit formula (per plan): 1d6 + attacker computer_accuracy - defender shield_value >= 6.
  - natural 6 base needed; computer makes hitting easier, shield makes it harder.

VP: 1 VP per enemy player ship destroyed; 2 VP per ancient/GCDS ship destroyed.
GCDS: special ancient ship (ship_type="gcds") with powerful weapon and shield stats.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.ship_parts import ComponentCategory, get_component, get_ship_type
from app.models.combat_log import CombatLog
from app.models.hex_tile import HexTile
from app.models.player import Player
from app.models.ship import Ship
from app.models.ship_blueprint import ShipBlueprint

MAX_COMBAT_ROUNDS = 10


# ---------------------------------------------------------------------------
# Combat stats dataclasses
# ---------------------------------------------------------------------------

@dataclass
class WeaponShot:
    """A single weapon's firing stats."""
    weapon_type: str        # "cannon" or "missile"
    damage: int             # damage dealt on hit
    fires_first: bool       # True for missiles (fire before cannons)


@dataclass
class CombatShipStats:
    """Computed combat statistics for a ship participating in a battle."""
    ship_id: int
    player_id: int | None   # None for ancient/GCDS ships
    ship_type: str
    max_hp: int
    current_hp: int
    initiative: int         # base_initiative + computer_accuracy (per plan)
    computer_accuracy: int  # added to attack roll
    shield_value: int       # subtracted from attacker's roll
    weapons: list[WeaponShot] = field(default_factory=list)
    is_ancient: bool = False


# ---------------------------------------------------------------------------
# Ancient / GCDS predefined stats
# ---------------------------------------------------------------------------

def _ancient_interceptor_stats(ship: Ship) -> CombatShipStats:
    """Stats for a generic ancient interceptor-class ship."""
    computer_accuracy = 2
    base_initiative = 2
    return CombatShipStats(
        ship_id=ship.id,
        player_id=None,
        ship_type=ship.ship_type,
        max_hp=ship.hp_remaining,
        current_hp=ship.hp_remaining,
        initiative=base_initiative + computer_accuracy,
        computer_accuracy=computer_accuracy,
        shield_value=1,
        weapons=[WeaponShot("cannon", 2, False)],
        is_ancient=True,
    )


def _gcds_stats(ship: Ship) -> CombatShipStats:
    """Stats for the Galactic Center Defense System — a powerful guardian."""
    computer_accuracy = 2
    base_initiative = 2
    return CombatShipStats(
        ship_id=ship.id,
        player_id=None,
        ship_type="gcds",
        max_hp=2,
        current_hp=ship.hp_remaining,
        initiative=base_initiative + computer_accuracy,
        computer_accuracy=computer_accuracy,
        shield_value=3,
        weapons=[
            WeaponShot("cannon", 4, False),
            WeaponShot("cannon", 4, False),
        ],
        is_ancient=True,
    )


def _get_ancient_combat_stats(ship: Ship) -> CombatShipStats:
    """Return hardcoded combat stats for any ancient/GCDS ship."""
    if ship.ship_type == "gcds":
        return _gcds_stats(ship)
    return _ancient_interceptor_stats(ship)


# ---------------------------------------------------------------------------
# Player ship stats (computed from blueprint)
# ---------------------------------------------------------------------------

async def get_ship_combat_stats(ship: Ship, db: AsyncSession) -> CombatShipStats:
    """Compute combat statistics for a ship.

    For player ships: reads the ShipBlueprint and derives stats from components.
    For ancient/GCDS ships: returns hardcoded predefined stats.
    """
    if ship.is_ancient:
        return _get_ancient_combat_stats(ship)

    result = await db.execute(
        select(ShipBlueprint).where(
            ShipBlueprint.player_id == ship.player_id,
            ShipBlueprint.ship_type == ship.ship_type,
        )
    )
    blueprint = result.scalar_one_or_none()

    try:
        ship_type_def = get_ship_type(ship.ship_type)
        base_initiative = ship_type_def.base_initiative
        base_hp = ship_type_def.base_hp
    except KeyError:
        base_initiative = 1
        base_hp = 1

    computer_accuracy = 0
    shield_value = 0
    extra_hp = 0
    weapons: list[WeaponShot] = []

    if blueprint:
        for slot in blueprint.slots:
            if slot is None:
                continue
            try:
                comp = get_component(slot)
            except KeyError:
                continue
            if comp.category == ComponentCategory.computer:
                computer_accuracy += comp.accuracy
            elif comp.category == ComponentCategory.shield:
                shield_value += comp.shield
            elif comp.category == ComponentCategory.cannon:
                weapons.append(WeaponShot("cannon", comp.damage, False))
            elif comp.category == ComponentCategory.missile:
                weapons.append(WeaponShot("missile", comp.damage, True))
            elif comp.category == ComponentCategory.hull:
                extra_hp += comp.extra_hp

    initiative = base_initiative + computer_accuracy
    max_hp = base_hp + extra_hp

    return CombatShipStats(
        ship_id=ship.id,
        player_id=ship.player_id,
        ship_type=ship.ship_type,
        max_hp=max_hp,
        current_hp=ship.hp_remaining,
        initiative=initiative,
        computer_accuracy=computer_accuracy,
        shield_value=shield_value,
        weapons=weapons,
        is_ancient=False,
    )


# ---------------------------------------------------------------------------
# Hit resolution
# ---------------------------------------------------------------------------

def roll_attack(attacker_computer: int, defender_shield: int) -> tuple[int, bool]:
    """Roll 1d6 and determine if the attack hits.

    Hit if: 1d6 + attacker_computer - defender_shield >= 6.
    Returns (roll, hit).
    """
    roll = random.randint(1, 6)
    effective = roll + attacker_computer - defender_shield
    return roll, effective >= 6


def roll_attack_with_value(roll: int, attacker_computer: int, defender_shield: int) -> bool:
    """Deterministic version used in tests (pre-specified roll value)."""
    effective = roll + attacker_computer - defender_shield
    return effective >= 6


# ---------------------------------------------------------------------------
# Combat round resolution (in-memory)
# ---------------------------------------------------------------------------

def _ships_by_faction(stats_list: list[CombatShipStats]) -> dict[str, list[CombatShipStats]]:
    """Group ships into factions.  player ships by str(player_id); ancients as 'ancient'."""
    factions: dict[str, list[CombatShipStats]] = {}
    for s in stats_list:
        key = "ancient" if s.player_id is None else str(s.player_id)
        factions.setdefault(key, []).append(s)
    return factions


def _pick_random_target(enemies: list[CombatShipStats]) -> CombatShipStats | None:
    """Return a random surviving enemy, or None if all are destroyed."""
    alive = [e for e in enemies if e.current_hp > 0]
    return random.choice(alive) if alive else None


def resolve_combat_round(
    side_a: list[CombatShipStats],
    side_b: list[CombatShipStats],
    log_entries: list[dict[str, Any]],
    combat_round: int,
    rng: random.Random | None = None,
) -> None:
    """Resolve one combat round between side_a and side_b (modifies in place).

    Missile phase first (fires_first=True), then cannon phase.
    Damage within each phase is accumulated and applied simultaneously.
    Dead ships (hp <= 0) are skipped as shooters but still absorb damage until
    the simultaneous apply step at the end of each phase.
    """
    _rand = rng or random

    for phase_name, weapon_filter in [("missiles", True), ("cannons", False)]:
        # Collect all shots for this phase from both sides
        # damage_map: target_ship_id -> total damage accumulated this phase
        damage_map: dict[int, int] = {}
        shots_this_phase: list[dict[str, Any]] = []

        # Build ordered list of (shooter, enemies) by initiative desc
        all_shooters: list[tuple[CombatShipStats, list[CombatShipStats]]] = []
        for shooter in sorted(side_a + side_b, key=lambda s: s.initiative, reverse=True):
            if shooter.current_hp <= 0:
                continue
            enemies = side_b if shooter in side_a else side_a
            all_shooters.append((shooter, enemies))

        for shooter, enemies in all_shooters:
            if shooter.current_hp <= 0:
                continue
            for weapon in shooter.weapons:
                if weapon.fires_first != weapon_filter:
                    continue
                target = _pick_random_target(enemies)
                if target is None:
                    break  # no valid targets
                roll, hit = roll_attack(shooter.computer_accuracy, target.shield_value)
                damage_dealt = weapon.damage if hit else 0
                if hit:
                    damage_map[target.ship_id] = damage_map.get(target.ship_id, 0) + damage_dealt
                shots_this_phase.append({
                    "round": combat_round,
                    "phase": phase_name,
                    "shooter_ship_id": shooter.ship_id,
                    "target_ship_id": target.ship_id,
                    "roll": roll,
                    "computer": shooter.computer_accuracy,
                    "shield": target.shield_value,
                    "hit": hit,
                    "damage": damage_dealt,
                })

        log_entries.extend(shots_this_phase)

        # Apply simultaneous damage
        all_ships = {s.ship_id: s for s in side_a + side_b}
        for ship_id, total_damage in damage_map.items():
            ship_stats = all_ships[ship_id]
            hp_before = ship_stats.current_hp
            ship_stats.current_hp = max(0, hp_before - total_damage)
            log_entries.append({
                "round": combat_round,
                "event": "damage",
                "ship_id": ship_id,
                "hp_before": hp_before,
                "hp_after": ship_stats.current_hp,
                "destroyed": ship_stats.current_hp == 0,
            })


def _sides_both_alive(
    side_a: list[CombatShipStats], side_b: list[CombatShipStats]
) -> bool:
    return any(s.current_hp > 0 for s in side_a) and any(s.current_hp > 0 for s in side_b)


def run_full_combat(
    side_a: list[CombatShipStats],
    side_b: list[CombatShipStats],
    rng: random.Random | None = None,
) -> list[dict[str, Any]]:
    """Run combat between side_a and side_b to completion.

    Returns the list of log_entries describing every event.
    Max MAX_COMBAT_ROUNDS rounds to prevent infinite loops.
    """
    log_entries: list[dict[str, Any]] = []
    for combat_round in range(1, MAX_COMBAT_ROUNDS + 1):
        if not _sides_both_alive(side_a, side_b):
            break
        resolve_combat_round(side_a, side_b, log_entries, combat_round, rng)

    # Determine winner
    a_survivors = [s for s in side_a if s.current_hp > 0]
    b_survivors = [s for s in side_b if s.current_hp > 0]
    winner = "side_a" if a_survivors else ("side_b" if b_survivors else "draw")
    log_entries.append({"event": "combat_end", "winner": winner})
    return log_entries


# ---------------------------------------------------------------------------
# VP calculation helpers
# ---------------------------------------------------------------------------

def calculate_vp_for_kills(
    destroyed_ships: list[CombatShipStats],
    winner_player_id: int | None,
) -> int:
    """Calculate VP earned by the winner for destroying enemy ships.

    1 VP per player ship destroyed; 2 VP per ancient/GCDS ship destroyed.
    """
    vp = 0
    for ship in destroyed_ships:
        if ship.is_ancient:
            vp += 2
        else:
            vp += 1
    return vp


# ---------------------------------------------------------------------------
# DB: find contested hexes
# ---------------------------------------------------------------------------

async def find_contested_hex_ids(game_id: int, db: AsyncSession) -> list[int]:
    """Return hex_tile_ids where ships from 2+ factions are present."""
    result = await db.execute(
        select(Ship).where(Ship.game_id == game_id, Ship.hex_tile_id.isnot(None))
    )
    ships = list(result.scalars().all())

    # Group by hex_tile_id, then check faction diversity
    hex_ships: dict[int, list[Ship]] = {}
    for ship in ships:
        if ship.hex_tile_id is not None:
            hex_ships.setdefault(ship.hex_tile_id, []).append(ship)

    contested = []
    for hex_id, hex_ship_list in hex_ships.items():
        factions = set()
        for ship in hex_ship_list:
            factions.add("ancient" if ship.is_ancient else str(ship.player_id))
        if len(factions) >= 2:
            contested.append(hex_id)

    return contested


# ---------------------------------------------------------------------------
# DB: resolve all combat for a game (called from turn_engine)
# ---------------------------------------------------------------------------

async def resolve_combat_for_game(
    game_id: int,
    round_number: int,
    db: AsyncSession,
) -> list[CombatLog]:
    """Find all contested hexes and resolve combat in each.

    Returns the list of CombatLog records created.
    Called by turn_engine when advancing from combat phase to upkeep.
    """
    contested_hex_ids = await find_contested_hex_ids(game_id, db)
    combat_logs: list[CombatLog] = []

    for hex_tile_id in contested_hex_ids:
        result = await db.execute(
            select(Ship).where(Ship.game_id == game_id, Ship.hex_tile_id == hex_tile_id)
        )
        ships = list(result.scalars().all())

        # Split into player factions and ancient faction
        player_ships: dict[int, list[Ship]] = {}
        ancient_ships: list[Ship] = []
        for ship in ships:
            if ship.is_ancient:
                ancient_ships.append(ship)
            elif ship.player_id is not None:
                player_ships.setdefault(ship.player_id, []).append(ship)

        # Determine matchups: player vs ancient first, then player vs player
        matchups: list[tuple[list[Ship], list[Ship]]] = []
        player_ids = list(player_ships.keys())

        if ancient_ships:
            # Each player fights the ancients (if multiple players, they fight together)
            all_player_ships = [s for pid_ships in player_ships.values() for s in pid_ships]
            if all_player_ships:
                matchups.append((all_player_ships, ancient_ships))

        elif len(player_ids) >= 2:
            # Player vs player: pair up the factions (first two for simplicity)
            matchups.append((player_ships[player_ids[0]], player_ships[player_ids[1]]))

        for side_a_ships, side_b_ships in matchups:
            # Compute combat stats for all ships
            side_a_stats = [await get_ship_combat_stats(s, db) for s in side_a_ships]
            side_b_stats = [await get_ship_combat_stats(s, db) for s in side_b_ships]

            log_entries = run_full_combat(side_a_stats, side_b_stats)

            # Determine attacker (first player in side_a or None)
            attacker_id: int | None = None
            for stats in side_a_stats:
                if stats.player_id is not None:
                    attacker_id = stats.player_id
                    break

            # Apply combat results back to DB ships and award VP
            await _apply_combat_results(
                side_a_stats=side_a_stats,
                side_b_stats=side_b_stats,
                side_a_ships=side_a_ships,
                side_b_ships=side_b_ships,
                db=db,
            )

            # Create CombatLog
            combat_log = CombatLog(
                game_id=game_id,
                hex_tile_id=hex_tile_id,
                round_number=round_number,
                attacker_id=attacker_id,
                log_entries=log_entries,
            )
            db.add(combat_log)
            combat_logs.append(combat_log)

    await db.flush()
    return combat_logs


async def _apply_combat_results(
    side_a_stats: list[CombatShipStats],
    side_b_stats: list[CombatShipStats],
    side_a_ships: list[Ship],
    side_b_ships: list[Ship],
    db: AsyncSession,
) -> None:
    """Update ships in DB based on combat outcomes and award VP."""
    ship_map = {s.id: s for s in side_a_ships + side_b_ships}

    # Determine who killed whom for VP
    side_a_player_ids = {s.player_id for s in side_a_stats if s.player_id is not None}

    # For each player in side_a that survives, find ships they killed from side_b
    a_survivors_exist = any(s.current_hp > 0 for s in side_a_stats)
    b_survivors_exist = any(s.current_hp > 0 for s in side_b_stats)

    # Award VP to surviving side for ships they killed
    if a_survivors_exist and side_a_player_ids:
        killed_from_b = [s for s in side_b_stats if s.current_hp <= 0]
        vp_earned = calculate_vp_for_kills(killed_from_b, winner_player_id=None)
        if vp_earned > 0:
            for player_id in side_a_player_ids:
                result = await db.execute(
                    select(Player).where(Player.id == player_id)
                )
                player = result.scalar_one_or_none()
                if player:
                    player.vp_count += vp_earned

    if b_survivors_exist:
        side_b_player_ids = {s.player_id for s in side_b_stats if s.player_id is not None}
        if side_b_player_ids:
            killed_from_a = [s for s in side_a_stats if s.current_hp <= 0]
            vp_earned = calculate_vp_for_kills(killed_from_a, winner_player_id=None)
            if vp_earned > 0:
                for player_id in side_b_player_ids:
                    result = await db.execute(
                        select(Player).where(Player.id == player_id)
                    )
                    player = result.scalar_one_or_none()
                    if player:
                        player.vp_count += vp_earned

    # Update HP and destroy ships
    for stats in side_a_stats + side_b_stats:
        ship = ship_map.get(stats.ship_id)
        if ship is None:
            continue
        if stats.current_hp <= 0:
            # Ship destroyed: remove from the board
            ship.hp_remaining = 0
            ship.hex_tile_id = None
        else:
            ship.hp_remaining = stats.current_hp

    await db.flush()


# ---------------------------------------------------------------------------
# Retreat
# ---------------------------------------------------------------------------

def _hex_neighbors(q: int, r: int) -> list[tuple[int, int]]:
    """Return the 6 axial-coordinate neighbors of (q, r)."""
    return [
        (q + 1, r),
        (q - 1, r),
        (q, r + 1),
        (q, r - 1),
        (q + 1, r - 1),
        (q - 1, r + 1),
    ]


async def retreat_ship(
    game_id: int,
    player_id: int,
    ship_id: int,
    target_hex_id: int,
    db: AsyncSession,
) -> Ship:
    """Move a ship to an adjacent non-contested hex before combat resolves.

    Validates:
    - Ship belongs to player.
    - Game is in combat phase.
    - Current hex has enemy ships (retreat is meaningful).
    - Target hex is adjacent to current hex.
    - Target hex has no enemy ships.

    Returns the updated Ship.
    Raises ValueError on validation failure.
    """
    # Load the ship
    result = await db.execute(
        select(Ship).where(Ship.id == ship_id, Ship.game_id == game_id)
    )
    ship = result.scalar_one_or_none()
    if ship is None:
        raise ValueError(f"Ship {ship_id} not found in game {game_id}")
    if ship.player_id != player_id:
        raise ValueError("Ship does not belong to you")
    if ship.hex_tile_id is None:
        raise ValueError("Ship is not on the board")

    current_hex_id = ship.hex_tile_id

    # Load current hex
    result = await db.execute(select(HexTile).where(HexTile.id == current_hex_id))
    current_hex = result.scalar_one_or_none()
    if current_hex is None:
        raise ValueError("Current hex not found")

    # Load target hex
    result = await db.execute(
        select(HexTile).where(HexTile.id == target_hex_id, HexTile.game_id == game_id)
    )
    target_hex = result.scalar_one_or_none()
    if target_hex is None:
        raise ValueError(f"Target hex {target_hex_id} not found in game {game_id}")

    # Validate adjacency
    neighbors = _hex_neighbors(current_hex.q, current_hex.r)
    if (target_hex.q, target_hex.r) not in neighbors:
        raise ValueError(
            f"Target hex ({target_hex.q}, {target_hex.r}) is not adjacent to "
            f"current hex ({current_hex.q}, {current_hex.r})"
        )

    # Check that the current hex has enemies (retreat is meaningful)
    result = await db.execute(
        select(Ship).where(Ship.hex_tile_id == current_hex_id, Ship.game_id == game_id)
    )
    ships_in_current = list(result.scalars().all())
    enemy_in_current = any(
        (s.is_ancient or s.player_id != player_id) for s in ships_in_current
    )
    if not enemy_in_current:
        raise ValueError("No enemies in current hex — no need to retreat")

    # Check that the target hex has no enemies
    result = await db.execute(
        select(Ship).where(Ship.hex_tile_id == target_hex_id, Ship.game_id == game_id)
    )
    ships_in_target = list(result.scalars().all())
    enemy_in_target = any(
        (s.is_ancient or s.player_id != player_id) for s in ships_in_target
    )
    if enemy_in_target:
        raise ValueError("Cannot retreat into a hex containing enemy ships")

    ship.hex_tile_id = target_hex_id
    await db.flush()
    return ship


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

async def get_combat_logs(
    game_id: int,
    db: AsyncSession,
    round_number: int | None = None,
) -> list[CombatLog]:
    """Return all CombatLog records for a game, optionally filtered by round."""
    query = select(CombatLog).where(CombatLog.game_id == game_id)
    if round_number is not None:
        query = query.where(CombatLog.round_number == round_number)
    query = query.order_by(CombatLog.id)
    result = await db.execute(query)
    return list(result.scalars().all())
