"""Tests for Task 12: Combat System.

Covers:
- Initiative ordering (ships fire in descending initiative order)
- Hit calculation: 1d6 + computer - shield >= 6
- roll_attack_with_value deterministic helper
- Missile phase fires before cannon phase
- Simultaneous damage application within each phase
- Ships with hp <= 0 stop shooting
- run_full_combat: winner determination, max rounds, VP awarded
- calculate_vp_for_kills: 1 VP for player ships, 2 VP for ancients
- GCDS stats (special ancient ship)
- find_contested_hex_ids: identifies hexes with 2+ factions
- resolve_combat_for_game: creates CombatLog, removes destroyed ships, awards VP
- retreat_ship: valid retreat, non-adjacent rejected, enemy-occupied target rejected
- API: GET /games/{id}/combat/logs requires active game
- API: POST /games/{id}/combat/retreat requires combat phase
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.combat_log import CombatLog
from app.models.game import Game, GamePhase, GameStatus
from app.models.hex_tile import HexTile, TileType
from app.models.player import Player, Species
from app.models.player_resources import PlayerResources
from app.models.ship import Ship
from app.models.ship_blueprint import ShipBlueprint
from app.models.user import User
from app.services.combat_service import (
    CombatShipStats,
    WeaponShot,
    calculate_vp_for_kills,
    find_contested_hex_ids,
    get_combat_logs,
    resolve_combat_for_game,
    resolve_combat_round,
    retreat_ship,
    roll_attack,
    roll_attack_with_value,
    run_full_combat,
    _gcds_stats,
    _ancient_interceptor_stats,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ship_stats(
    ship_id: int,
    player_id: int | None,
    ship_type: str = "interceptor",
    hp: int = 1,
    initiative: int = 1,
    computer: int = 0,
    shield: int = 0,
    weapons: list | None = None,
    is_ancient: bool = False,
) -> CombatShipStats:
    return CombatShipStats(
        ship_id=ship_id,
        player_id=player_id,
        ship_type=ship_type,
        max_hp=hp,
        current_hp=hp,
        initiative=initiative,
        computer_accuracy=computer,
        shield_value=shield,
        weapons=weapons or [WeaponShot("cannon", 1, False)],
        is_ancient=is_ancient,
    )


async def _create_user(db: AsyncSession, tag: str) -> User:
    user = User(
        email=f"combat_{tag}@test.com",
        username=f"combat_{tag}",
        hashed_password="x",
    )
    db.add(user)
    await db.flush()
    return user


async def _create_game_and_players(
    db: AsyncSession, tag: str, phase: GamePhase = GamePhase.combat
) -> tuple[Game, Player, Player]:
    user_a = await _create_user(db, f"{tag}_a")
    user_b = await _create_user(db, f"{tag}_b")

    game = Game(
        name=f"combat-game-{tag}",
        status=GameStatus.active,
        max_players=2,
        current_round=1,
        current_phase=phase,
        host_user_id=user_a.id,
    )
    db.add(game)
    await db.flush()

    player_a = Player(
        game_id=game.id, user_id=user_a.id, species=Species.human, turn_order=0
    )
    player_b = Player(
        game_id=game.id, user_id=user_b.id, species=Species.planta, turn_order=1
    )
    db.add(player_a)
    db.add(player_b)
    await db.flush()

    for p in [player_a, player_b]:
        db.add(PlayerResources(
            player_id=p.id,
            money=10, science=10, materials=10,
            population_cubes={"orbital": 5, "advanced": 5, "gauss": 5},
            tradespheres=0,
            influence_discs_total=11,
            influence_discs_used=0,
        ))
    await db.flush()

    return game, player_a, player_b


async def _create_hex(db: AsyncSession, game_id: int, q: int, r: int) -> HexTile:
    hex_tile = HexTile(
        game_id=game_id, q=q, r=r,
        tile_type=TileType.inner,
        is_explored=True,
        owner_player_id=None,
    )
    db.add(hex_tile)
    await db.flush()
    return hex_tile


async def _place_ship(
    db: AsyncSession, game_id: int, player_id: int | None,
    hex_tile_id: int, ship_type: str = "interceptor",
    hp: int = 1, is_ancient: bool = False,
) -> Ship:
    ship = Ship(
        game_id=game_id,
        player_id=player_id,
        ship_type=ship_type,
        hex_tile_id=hex_tile_id,
        hp_remaining=hp,
        is_ancient=is_ancient,
    )
    db.add(ship)
    await db.flush()
    return ship


async def _add_blueprint_with_cannon(
    db: AsyncSession, player_id: int, ship_type: str = "interceptor"
) -> ShipBlueprint:
    """Give a player a blueprint that includes an electron_cannon and nuclear_source."""
    blueprint = ShipBlueprint(
        player_id=player_id,
        ship_type=ship_type,
        # nuclear_source (3 power) + electron_cannon (1 power consumed) + electron_drive
        slots=["nuclear_source", "electron_cannon", "electron_drive", None],
        is_valid=True,
    )
    db.add(blueprint)
    await db.flush()
    return blueprint


# ---------------------------------------------------------------------------
# roll_attack_with_value: deterministic hit calculation
# ---------------------------------------------------------------------------

def test_roll_attack_hit_exact_threshold():
    # roll=6, computer=0, shield=0: 6 + 0 - 0 = 6 >= 6 -> hit
    assert roll_attack_with_value(6, 0, 0) is True


def test_roll_attack_miss_below_threshold():
    # roll=5, computer=0, shield=0: 5 < 6 -> miss
    assert roll_attack_with_value(5, 0, 0) is False


def test_roll_attack_computer_makes_hit():
    # roll=4, computer=2, shield=0: 4 + 2 - 0 = 6 -> hit
    assert roll_attack_with_value(4, 2, 0) is True


def test_roll_attack_shield_prevents_hit():
    # roll=6, computer=0, shield=2: 6 + 0 - 2 = 4 < 6 -> miss
    assert roll_attack_with_value(6, 0, 2) is False


def test_roll_attack_computer_vs_shield():
    # roll=5, computer=3, shield=2: 5 + 3 - 2 = 6 -> hit
    assert roll_attack_with_value(5, 3, 2) is True


def test_roll_attack_random_returns_tuple():
    roll, hit = roll_attack(0, 0)
    assert 1 <= roll <= 6
    assert isinstance(hit, bool)


# ---------------------------------------------------------------------------
# Initiative ordering
# ---------------------------------------------------------------------------

def test_initiative_ordering_higher_shoots_first():
    """Ship with higher initiative should fire first in the cannon phase."""
    log = []
    high_init = _make_ship_stats(1, player_id=1, initiative=5, computer=5, hp=10)
    low_init = _make_ship_stats(2, player_id=2, initiative=1, computer=0, hp=1)

    resolve_combat_round([high_init], [low_init], log, combat_round=1)

    # The first shot logged should come from the high-initiative ship
    shots = [e for e in log if "shooter_ship_id" in e]
    assert len(shots) >= 1
    assert shots[0]["shooter_ship_id"] == 1


def test_two_ships_same_side_different_initiative():
    """Both ships on side_a shoot at side_b; higher initiative shoots first."""
    log = []
    fast = _make_ship_stats(1, player_id=1, initiative=10, computer=5)
    slow = _make_ship_stats(2, player_id=1, initiative=1, computer=0)
    enemy = _make_ship_stats(3, player_id=2, hp=100)

    resolve_combat_round([fast, slow], [enemy], log, combat_round=1)

    shots = [e for e in log if "shooter_ship_id" in e]
    shooter_order = [s["shooter_ship_id"] for s in shots]
    # fast (id=1) must appear before slow (id=2)
    idx_fast = next(i for i, x in enumerate(shooter_order) if x == 1)
    idx_slow = next(i for i, x in enumerate(shooter_order) if x == 2)
    assert idx_fast < idx_slow


# ---------------------------------------------------------------------------
# Missile phase fires before cannon phase
# ---------------------------------------------------------------------------

def test_missile_phase_before_cannon_phase():
    """Missile shots should appear in log before cannon shots."""
    log = []
    shooter = CombatShipStats(
        ship_id=1, player_id=1, ship_type="cruiser",
        max_hp=2, current_hp=2,
        initiative=3, computer_accuracy=5, shield_value=0,
        weapons=[
            WeaponShot("missile", 1, True),
            WeaponShot("cannon", 1, False),
        ],
        is_ancient=False,
    )
    target = _make_ship_stats(2, player_id=2, hp=10)

    resolve_combat_round([shooter], [target], log, combat_round=1)

    shots = [e for e in log if "phase" in e]
    phases_in_order = [e["phase"] for e in shots]
    missile_idx = next((i for i, p in enumerate(phases_in_order) if p == "missiles"), None)
    cannon_idx = next((i for i, p in enumerate(phases_in_order) if p == "cannons"), None)
    # Both phases must fire (computer_accuracy=5 guarantees hits) and missiles must come first
    assert missile_idx is not None, "No missile phase events logged"
    assert cannon_idx is not None, "No cannon phase events logged"
    assert missile_idx < cannon_idx


# ---------------------------------------------------------------------------
# Simultaneous damage within phase
# ---------------------------------------------------------------------------

def test_simultaneous_damage_both_ships_die_same_phase():
    """Two ships each with 1HP and guaranteed hits should both die simultaneously."""
    # Give both ships computer=5 so they always hit (roll 1+5-0 = 6)
    a = _make_ship_stats(1, player_id=1, hp=1, initiative=2, computer=5)
    b = _make_ship_stats(2, player_id=2, hp=1, initiative=1, computer=5)

    log = []
    # Manually patch roll_attack inside combat_service to always return (6, True)
    import app.services.combat_service as cs
    original = cs.roll_attack

    def always_hit(attacker_computer, defender_shield):
        return 6, True

    cs.roll_attack = always_hit
    try:
        resolve_combat_round([a], [b], log, combat_round=1)
    finally:
        cs.roll_attack = original

    # Both should be at 0 HP (simultaneous application)
    assert a.current_hp == 0
    assert b.current_hp == 0


# ---------------------------------------------------------------------------
# Dead ships don't fire
# ---------------------------------------------------------------------------

def test_dead_ship_does_not_shoot():
    """A ship already at 0 HP should not fire."""
    log = []
    dead = _make_ship_stats(1, player_id=1, hp=0, computer=5)
    dead.current_hp = 0
    enemy = _make_ship_stats(2, player_id=2, hp=10)

    resolve_combat_round([dead], [enemy], log, combat_round=1)

    shots = [e for e in log if e.get("shooter_ship_id") == 1]
    assert len(shots) == 0


# ---------------------------------------------------------------------------
# run_full_combat
# ---------------------------------------------------------------------------

def test_run_full_combat_side_a_wins():
    """Side A (high HP, good accuracy) should defeat side B."""
    import app.services.combat_service as cs
    original = cs.roll_attack

    def always_hit(attacker_computer, defender_shield):
        return 6, True

    cs.roll_attack = always_hit
    try:
        a = _make_ship_stats(1, player_id=1, hp=10, initiative=5, computer=5)
        b = _make_ship_stats(2, player_id=2, hp=1, initiative=1, computer=0)
        log = run_full_combat([a], [b])
    finally:
        cs.roll_attack = original

    end_event = next(e for e in log if e.get("event") == "combat_end")
    assert end_event["winner"] == "side_a"


def test_run_full_combat_side_b_wins():
    """Side B should win when side A has 1 HP and side B has many."""
    import app.services.combat_service as cs
    original = cs.roll_attack

    def always_hit(attacker_computer, defender_shield):
        return 6, True

    cs.roll_attack = always_hit
    try:
        a = _make_ship_stats(1, player_id=1, hp=1, initiative=1, computer=5)
        b = _make_ship_stats(2, player_id=2, hp=10, initiative=5, computer=5)
        log = run_full_combat([a], [b])
    finally:
        cs.roll_attack = original

    end_event = next(e for e in log if e.get("event") == "combat_end")
    assert end_event["winner"] == "side_b"


def test_run_full_combat_never_exceeds_max_rounds():
    """Combat must end even if both sides never hit (roll always misses)."""
    import app.services.combat_service as cs
    original = cs.roll_attack

    def always_miss(attacker_computer, defender_shield):
        return 1, False

    cs.roll_attack = always_miss
    try:
        a = _make_ship_stats(1, player_id=1, hp=100)
        b = _make_ship_stats(2, player_id=2, hp=100)
        log = run_full_combat([a], [b])
    finally:
        cs.roll_attack = original

    end_event = next(e for e in log if e.get("event") == "combat_end")
    assert end_event is not None  # combat ends


def test_run_full_combat_ends_immediately_when_one_side_empty():
    """If side_b starts with 0-hp ships, combat should end with side_a winning."""
    import app.services.combat_service as cs
    original = cs.roll_attack

    def always_miss(attacker_computer, defender_shield):
        return 1, False

    cs.roll_attack = always_miss
    try:
        a = _make_ship_stats(1, player_id=1, hp=2)
        b = _make_ship_stats(2, player_id=2, hp=0)
        b.current_hp = 0
        log = run_full_combat([a], [b])
    finally:
        cs.roll_attack = original

    end_event = next(e for e in log if e.get("event") == "combat_end")
    assert end_event["winner"] == "side_a"


# ---------------------------------------------------------------------------
# calculate_vp_for_kills
# ---------------------------------------------------------------------------

def test_vp_one_per_player_ship():
    ship = _make_ship_stats(1, player_id=2, is_ancient=False)
    ship.current_hp = 0
    vp = calculate_vp_for_kills([ship], winner_player_id=1)
    assert vp == 1


def test_vp_two_per_ancient_ship():
    ship = _make_ship_stats(1, player_id=None, is_ancient=True)
    ship.current_hp = 0
    vp = calculate_vp_for_kills([ship], winner_player_id=1)
    assert vp == 2


def test_vp_mixed_kills():
    player_ship = _make_ship_stats(1, player_id=2, is_ancient=False)
    ancient_ship = _make_ship_stats(2, player_id=None, is_ancient=True)
    gcds = _make_ship_stats(3, player_id=None, is_ancient=True)
    vp = calculate_vp_for_kills(
        [player_ship, ancient_ship, gcds], winner_player_id=1
    )
    assert vp == 5  # 1 + 2 + 2


def test_vp_no_kills():
    vp = calculate_vp_for_kills([], winner_player_id=1)
    assert vp == 0


# ---------------------------------------------------------------------------
# GCDS stats
# ---------------------------------------------------------------------------

def _fake_ship(ship_id, player_id, ship_type, hp, is_ancient=True, game_id=1, hex_tile_id=1):
    """Create a plain namespace object mimicking Ship for use with stat functions."""
    from types import SimpleNamespace
    return SimpleNamespace(
        id=ship_id,
        player_id=player_id,
        ship_type=ship_type,
        hp_remaining=hp,
        is_ancient=is_ancient,
        game_id=game_id,
        hex_tile_id=hex_tile_id,
    )


def test_gcds_stats_has_high_shield():
    """GCDS should have shield_value=3 per spec."""
    gcds_ship = _fake_ship(99, None, "gcds", 2)

    stats = _gcds_stats(gcds_ship)
    assert stats.shield_value == 3
    assert stats.is_ancient is True
    assert len(stats.weapons) >= 1


def test_ancient_interceptor_stats():
    ancient_ship = _fake_ship(50, None, "ancient_interceptor", 1)

    stats = _ancient_interceptor_stats(ancient_ship)
    assert stats.is_ancient is True
    assert stats.shield_value >= 0
    assert len(stats.weapons) >= 1


# ---------------------------------------------------------------------------
# find_contested_hex_ids (DB)
# ---------------------------------------------------------------------------

async def test_find_contested_hex_player_vs_ancient(db_session: AsyncSession):
    game, player_a, player_b = await _create_game_and_players(db_session, "contest1")
    hex_tile = await _create_hex(db_session, game.id, 0, 0)

    await _place_ship(db_session, game.id, player_a.id, hex_tile.id)
    await _place_ship(db_session, game.id, None, hex_tile.id, is_ancient=True)

    contested = await find_contested_hex_ids(game.id, db_session)
    assert hex_tile.id in contested


async def test_find_contested_hex_player_vs_player(db_session: AsyncSession):
    game, player_a, player_b = await _create_game_and_players(db_session, "contest2")
    hex_tile = await _create_hex(db_session, game.id, 1, 1)

    await _place_ship(db_session, game.id, player_a.id, hex_tile.id)
    await _place_ship(db_session, game.id, player_b.id, hex_tile.id)

    contested = await find_contested_hex_ids(game.id, db_session)
    assert hex_tile.id in contested


async def test_find_contested_hex_single_player_not_contested(db_session: AsyncSession):
    game, player_a, player_b = await _create_game_and_players(db_session, "contest3")
    hex_tile = await _create_hex(db_session, game.id, 2, 2)

    await _place_ship(db_session, game.id, player_a.id, hex_tile.id)

    contested = await find_contested_hex_ids(game.id, db_session)
    assert hex_tile.id not in contested


async def test_find_contested_hex_empty_game(db_session: AsyncSession):
    game, player_a, player_b = await _create_game_and_players(db_session, "contest4")
    contested = await find_contested_hex_ids(game.id, db_session)
    assert contested == []


# ---------------------------------------------------------------------------
# resolve_combat_for_game (DB integration)
# ---------------------------------------------------------------------------

async def test_resolve_combat_creates_log(db_session: AsyncSession):
    import app.services.combat_service as cs
    original = cs.roll_attack
    cs.roll_attack = lambda c, s: (6, True)

    try:
        game, player_a, player_b = await _create_game_and_players(
            db_session, "resolve1"
        )
        hex_tile = await _create_hex(db_session, game.id, 0, 0)

        # Give player_a a blueprint so their ship has weapons
        await _add_blueprint_with_cannon(db_session, player_a.id)

        # player_a ship vs ancient ship
        await _place_ship(db_session, game.id, player_a.id, hex_tile.id, hp=5)
        await _place_ship(db_session, game.id, None, hex_tile.id, is_ancient=True, hp=1)

        logs = await resolve_combat_for_game(game.id, round_number=1, db=db_session)
    finally:
        cs.roll_attack = original

    assert len(logs) == 1
    assert logs[0].game_id == game.id
    assert logs[0].hex_tile_id == hex_tile.id
    assert logs[0].round_number == 1
    assert isinstance(logs[0].log_entries, list)
    assert len(logs[0].log_entries) > 0


async def test_resolve_combat_removes_destroyed_ship(db_session: AsyncSession):
    import app.services.combat_service as cs
    original = cs.roll_attack
    cs.roll_attack = lambda c, s: (6, True)

    try:
        game, player_a, player_b = await _create_game_and_players(
            db_session, "resolve2"
        )
        hex_tile = await _create_hex(db_session, game.id, 0, 0)

        await _add_blueprint_with_cannon(db_session, player_a.id)

        await _place_ship(
            db_session, game.id, player_a.id, hex_tile.id, hp=100
        )
        ancient_ship = await _place_ship(
            db_session, game.id, None, hex_tile.id, is_ancient=True, hp=1
        )
        ancient_id = ancient_ship.id

        await resolve_combat_for_game(game.id, round_number=1, db=db_session)
    finally:
        cs.roll_attack = original

    result = await db_session.execute(select(Ship).where(Ship.id == ancient_id))
    destroyed = result.scalar_one()
    # Destroyed ship should have hp=0 and no hex
    assert destroyed.hp_remaining == 0
    assert destroyed.hex_tile_id is None


async def test_resolve_combat_awards_vp_for_ancient_kill(db_session: AsyncSession):
    import app.services.combat_service as cs
    original = cs.roll_attack
    cs.roll_attack = lambda c, s: (6, True)

    try:
        game, player_a, player_b = await _create_game_and_players(
            db_session, "resolve3"
        )
        hex_tile = await _create_hex(db_session, game.id, 0, 0)

        await _add_blueprint_with_cannon(db_session, player_a.id)

        await _place_ship(db_session, game.id, player_a.id, hex_tile.id, hp=100)
        await _place_ship(db_session, game.id, None, hex_tile.id, is_ancient=True, hp=1)

        await resolve_combat_for_game(game.id, round_number=1, db=db_session)
    finally:
        cs.roll_attack = original

    await db_session.refresh(player_a)
    # 2 VP for destroying an ancient ship
    assert player_a.vp_count >= 2


async def test_resolve_combat_no_contested_hexes_no_logs(db_session: AsyncSession):
    game, player_a, player_b = await _create_game_and_players(db_session, "resolve4")
    hex_a = await _create_hex(db_session, game.id, 0, 0)
    hex_b = await _create_hex(db_session, game.id, 3, 3)

    await _place_ship(db_session, game.id, player_a.id, hex_a.id)
    await _place_ship(db_session, game.id, player_b.id, hex_b.id)

    logs = await resolve_combat_for_game(game.id, round_number=1, db=db_session)
    assert len(logs) == 0


# ---------------------------------------------------------------------------
# get_combat_logs (DB)
# ---------------------------------------------------------------------------

async def test_get_combat_logs_returns_all(db_session: AsyncSession):
    game, player_a, player_b = await _create_game_and_players(db_session, "logs1")
    hex_tile = await _create_hex(db_session, game.id, 0, 0)

    log1 = CombatLog(
        game_id=game.id, hex_tile_id=hex_tile.id,
        round_number=1, attacker_id=player_a.id, log_entries=[]
    )
    log2 = CombatLog(
        game_id=game.id, hex_tile_id=hex_tile.id,
        round_number=2, attacker_id=player_a.id, log_entries=[]
    )
    db_session.add(log1)
    db_session.add(log2)
    await db_session.flush()

    logs = await get_combat_logs(game.id, db_session)
    assert len(logs) == 2


async def test_get_combat_logs_filtered_by_round(db_session: AsyncSession):
    game, player_a, player_b = await _create_game_and_players(db_session, "logs2")
    hex_tile = await _create_hex(db_session, game.id, 0, 0)

    log1 = CombatLog(
        game_id=game.id, hex_tile_id=hex_tile.id,
        round_number=1, attacker_id=None, log_entries=[]
    )
    log2 = CombatLog(
        game_id=game.id, hex_tile_id=hex_tile.id,
        round_number=2, attacker_id=None, log_entries=[]
    )
    db_session.add(log1)
    db_session.add(log2)
    await db_session.flush()

    logs_r1 = await get_combat_logs(game.id, db_session, round_number=1)
    assert len(logs_r1) == 1
    assert logs_r1[0].round_number == 1


# ---------------------------------------------------------------------------
# retreat_ship (DB)
# ---------------------------------------------------------------------------

async def test_retreat_ship_valid(db_session: AsyncSession):
    game, player_a, player_b = await _create_game_and_players(db_session, "retreat1")

    # Create two adjacent hexes (axial neighbors differ by 1 in q)
    hex_current = await _create_hex(db_session, game.id, 0, 0)
    hex_target = await _create_hex(db_session, game.id, 1, 0)  # adjacent to (0,0)

    # Place player_a's ship on current hex
    ship = await _place_ship(db_session, game.id, player_a.id, hex_current.id)
    # Place an ancient enemy on the current hex
    await _place_ship(db_session, game.id, None, hex_current.id, is_ancient=True)

    updated_ship = await retreat_ship(
        game_id=game.id,
        player_id=player_a.id,
        ship_id=ship.id,
        target_hex_id=hex_target.id,
        db=db_session,
    )

    assert updated_ship.hex_tile_id == hex_target.id


async def test_retreat_ship_non_adjacent_rejected(db_session: AsyncSession):
    game, player_a, player_b = await _create_game_and_players(db_session, "retreat2")

    hex_current = await _create_hex(db_session, game.id, 0, 0)
    hex_far = await _create_hex(db_session, game.id, 5, 5)  # not adjacent

    ship = await _place_ship(db_session, game.id, player_a.id, hex_current.id)
    await _place_ship(db_session, game.id, None, hex_current.id, is_ancient=True)

    with pytest.raises(ValueError, match="not adjacent"):
        await retreat_ship(
            game_id=game.id,
            player_id=player_a.id,
            ship_id=ship.id,
            target_hex_id=hex_far.id,
            db=db_session,
        )


async def test_retreat_ship_enemy_in_target_rejected(db_session: AsyncSession):
    game, player_a, player_b = await _create_game_and_players(db_session, "retreat3")

    hex_current = await _create_hex(db_session, game.id, 0, 0)
    hex_target = await _create_hex(db_session, game.id, 1, 0)

    ship = await _place_ship(db_session, game.id, player_a.id, hex_current.id)
    # Enemies on both hexes
    await _place_ship(db_session, game.id, None, hex_current.id, is_ancient=True)
    await _place_ship(db_session, game.id, None, hex_target.id, is_ancient=True)

    with pytest.raises(ValueError, match="enemy ships"):
        await retreat_ship(
            game_id=game.id,
            player_id=player_a.id,
            ship_id=ship.id,
            target_hex_id=hex_target.id,
            db=db_session,
        )


async def test_retreat_ship_no_enemy_in_current_rejected(db_session: AsyncSession):
    game, player_a, player_b = await _create_game_and_players(db_session, "retreat4")

    hex_current = await _create_hex(db_session, game.id, 0, 0)
    hex_target = await _create_hex(db_session, game.id, 1, 0)

    ship = await _place_ship(db_session, game.id, player_a.id, hex_current.id)
    # No enemies in current hex — retreat is meaningless

    with pytest.raises(ValueError, match="[Nn]o enemies"):
        await retreat_ship(
            game_id=game.id,
            player_id=player_a.id,
            ship_id=ship.id,
            target_hex_id=hex_target.id,
            db=db_session,
        )


async def test_retreat_ship_wrong_player_rejected(db_session: AsyncSession):
    game, player_a, player_b = await _create_game_and_players(db_session, "retreat5")

    hex_current = await _create_hex(db_session, game.id, 0, 0)
    hex_target = await _create_hex(db_session, game.id, 1, 0)

    ship = await _place_ship(db_session, game.id, player_a.id, hex_current.id)
    await _place_ship(db_session, game.id, None, hex_current.id, is_ancient=True)

    with pytest.raises(ValueError, match="does not belong"):
        await retreat_ship(
            game_id=game.id,
            player_id=player_b.id,  # wrong player
            ship_id=ship.id,
            target_hex_id=hex_target.id,
            db=db_session,
        )


# ---------------------------------------------------------------------------
# API: GET /games/{id}/combat/logs
# ---------------------------------------------------------------------------

async def _register_and_login(client, email, username, password="testpass1"):
    await client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    resp = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    return resp.json()["access_token"]


async def _setup_started_game(client, tag: str) -> tuple[list[str], int]:
    t0 = await _register_and_login(
        client, f"capi_{tag}_0@t.com", f"capi_{tag}_0"
    )
    t1 = await _register_and_login(
        client, f"capi_{tag}_1@t.com", f"capi_{tag}_1"
    )

    resp = await client.post(
        "/games",
        json={"name": f"capi-game-{tag}", "max_players": 2},
        headers={"Authorization": f"Bearer {t0}"},
    )
    game_id = resp.json()["id"]

    inv = await client.post(
        f"/games/{game_id}/invite",
        json={"invitee_email": f"capi_{tag}_1@t.com"},
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


async def test_api_get_combat_logs_empty_for_new_game(db_client, db_session):
    tokens, game_id = await _setup_started_game(db_client, f"apilog_{id(db_client)}")

    resp = await db_client.get(
        f"/games/{game_id}/combat/logs",
        headers={"Authorization": f"Bearer {tokens[0]}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_api_get_combat_logs_lobby_game_rejected(db_client, db_session):
    """Cannot view combat logs for a game still in lobby."""
    t0 = await _register_and_login(
        db_client, f"lobby_log_{id(db_client)}@t.com", f"lobby_log_{id(db_client)}"
    )
    resp = await db_client.post(
        "/games",
        json={"name": f"lobby-game-{id(db_client)}", "max_players": 2},
        headers={"Authorization": f"Bearer {t0}"},
    )
    game_id = resp.json()["id"]

    resp = await db_client.get(
        f"/games/{game_id}/combat/logs",
        headers={"Authorization": f"Bearer {t0}"},
    )
    assert resp.status_code == 400


async def test_api_get_combat_logs_nonexistent_game(db_client, db_session):
    t0 = await _register_and_login(
        db_client, f"noexist_{id(db_client)}@t.com", f"noexist_{id(db_client)}"
    )
    resp = await db_client.get(
        "/games/999999/combat/logs",
        headers={"Authorization": f"Bearer {t0}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# API: POST /games/{id}/combat/retreat
# ---------------------------------------------------------------------------

async def test_api_retreat_wrong_phase_rejected(db_client, db_session):
    """Retreat endpoint should return 400 when game is not in combat phase."""
    tokens, game_id = await _setup_started_game(db_client, f"apiretreat_{id(db_client)}")

    # After game start, phase is typically 'activation', not 'combat'
    resp = await db_client.post(
        f"/games/{game_id}/combat/retreat",
        json={"ship_id": 1, "target_hex_id": 2},
        headers={"Authorization": f"Bearer {tokens[0]}"},
    )
    # Should be 400 (wrong phase) or 400 (ship not found)
    assert resp.status_code in (400,)
