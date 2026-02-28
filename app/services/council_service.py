"""Galactic Council service for Eclipse: Second Dawn.

Once the Galactic Center is explored the Galactic Council convenes every Upkeep.
Players place ambassador tokens on one of two sides of the active resolution card.
The side with the most ambassadors wins, its effect is applied, and each player on
the winning side earns 1 VP per ambassador they placed there.
"""

from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.resolutions import (
    get_resolution,
    get_resolution_ids,
)
from app.models.council import CouncilState
from app.models.game import Game
from app.models.player import Player
from app.models.player_resources import PlayerResources


# ---------------------------------------------------------------------------
# Council state helpers
# ---------------------------------------------------------------------------


async def get_council_state(db: AsyncSession, game_id: int) -> CouncilState | None:
    """Return the CouncilState for the given game, or None if not created yet."""
    result = await db.execute(
        select(CouncilState).where(CouncilState.game_id == game_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_council_state(db: AsyncSession, game_id: int) -> CouncilState:
    """Return existing CouncilState or create a new one for the game."""
    state = await get_council_state(db, game_id)
    if state is None:
        state = CouncilState(
            game_id=game_id,
            galactic_center_explored=False,
            current_resolution_id=None,
            ambassador_placements={},
            vp_from_council={},
            ambassadors_per_player=6,
            last_vote_round=None,
        )
        db.add(state)
        await db.flush()
    return state


async def mark_galactic_center_explored(db: AsyncSession, game_id: int) -> CouncilState:
    """Call this when the Galactic Center tile is revealed/explored."""
    state = await get_or_create_council_state(db, game_id)
    state.galactic_center_explored = True
    await db.flush()
    return state


# ---------------------------------------------------------------------------
# Ambassador placement
# ---------------------------------------------------------------------------


def _ambassadors_placed(state: CouncilState, player_id: int) -> int:
    """Total ambassadors a player has placed in the current vote."""
    pid = str(player_id)
    placements = state.ambassador_placements.get(pid, {})
    return placements.get("side_a", 0) + placements.get("side_b", 0)


def _ambassadors_available(state: CouncilState, player_id: int) -> int:
    return state.ambassadors_per_player - _ambassadors_placed(state, player_id)


async def place_ambassadors(
    db: AsyncSession,
    game_id: int,
    player_id: int,
    side: str,
    count: int,
) -> CouncilState:
    """Place *count* ambassadors for *player_id* on *side* ('side_a' or 'side_b').

    Validates that:
    - A resolution is currently active
    - The side is valid ('side_a' or 'side_b')
    - The player has enough ambassador tokens remaining
    """
    if side not in ("side_a", "side_b"):
        raise ValueError("side must be 'side_a' or 'side_b'")
    if count < 1:
        raise ValueError("count must be at least 1")

    state = await get_or_create_council_state(db, game_id)
    if not state.galactic_center_explored:
        raise ValueError("Galactic Center has not been explored yet; no council in session")
    if state.current_resolution_id is None:
        raise ValueError("No resolution is currently active")

    available = _ambassadors_available(state, player_id)
    if count > available:
        raise ValueError(
            f"Player only has {available} ambassador(s) remaining this vote"
        )

    pid = str(player_id)
    # ambassador_placements is JSON — mutate a copy then reassign for SQLAlchemy detection
    new_placements = dict(state.ambassador_placements)
    player_entry = dict(new_placements.get(pid, {"side_a": 0, "side_b": 0}))
    player_entry[side] = player_entry.get(side, 0) + count
    new_placements[pid] = player_entry
    state.ambassador_placements = new_placements

    await db.flush()
    return state


# ---------------------------------------------------------------------------
# Resolution selection
# ---------------------------------------------------------------------------


async def start_new_vote(
    db: AsyncSession,
    game_id: int,
    resolution_id: str | None = None,
) -> CouncilState:
    """Begin a new council vote round.  Clears ambassador placements and selects
    a resolution (randomly if not specified).
    """
    state = await get_or_create_council_state(db, game_id)

    if resolution_id is None:
        # Pick a random resolution
        ids = get_resolution_ids()
        resolution_id = random.choice(ids)

    # Validate the resolution exists
    get_resolution(resolution_id)  # raises KeyError if unknown

    state.current_resolution_id = resolution_id
    state.ambassador_placements = {}
    await db.flush()
    return state


# ---------------------------------------------------------------------------
# Voting tally & VP distribution
# ---------------------------------------------------------------------------


def tally_votes(
    ambassador_placements: dict,
) -> tuple[str | None, dict[str, int], dict[str, int]]:
    """Count ambassadors for each side and determine the winner.

    Returns:
        (winning_side, side_a_totals, side_b_totals)
        winning_side is 'side_a', 'side_b', or None on a tie.
        side_a_totals / side_b_totals: {player_id_str: ambassador_count}
    """
    side_a_totals: dict[str, int] = {}
    side_b_totals: dict[str, int] = {}

    for pid, placed in ambassador_placements.items():
        a = placed.get("side_a", 0)
        b = placed.get("side_b", 0)
        if a:
            side_a_totals[pid] = a
        if b:
            side_b_totals[pid] = b

    total_a = sum(side_a_totals.values())
    total_b = sum(side_b_totals.values())

    if total_a > total_b:
        winning_side = "side_a"
    elif total_b > total_a:
        winning_side = "side_b"
    else:
        winning_side = None  # tie — resolution fails

    return winning_side, side_a_totals, side_b_totals


async def _apply_effect_to_winners(
    db: AsyncSession,
    effect_params: dict,
    winner_player_ids: list[int],
) -> None:
    """Apply a resolution effect (income bonus or VP bonus) to winners."""
    effect_type = effect_params.get("effect_type", "none")
    params = effect_params.get("params", {})

    if effect_type == "none":
        return

    if effect_type == "income_bonus":
        resource = params.get("resource", "money")
        amount = params.get("amount", 0)
        for player_id in winner_player_ids:
            result = await db.execute(
                select(PlayerResources).where(PlayerResources.player_id == player_id)
            )
            resources = result.scalar_one_or_none()
            if resources is None:
                continue
            if resource == "money":
                resources.money += amount
            elif resource == "science":
                resources.science += amount
            elif resource == "materials":
                resources.materials += amount
            await db.flush()

    elif effect_type == "vp_bonus":
        vp = params.get("vp", 0)
        for player_id in winner_player_ids:
            result = await db.execute(
                select(Player).where(Player.id == player_id)
            )
            player = result.scalar_one_or_none()
            if player is None:
                continue
            player.vp_count += vp
            await db.flush()

    # "special" effects (like no_build_this_round) are noted in the log
    # but not currently enforced by the engine (future enhancement)


async def resolve_vote(
    db: AsyncSession,
    game_id: int,
    current_round: int,
) -> dict:
    """Tally the current vote, apply effects, award council VPs, and close the vote.

    Returns a summary dict describing the outcome.
    """
    state = await get_or_create_council_state(db, game_id)

    if not state.galactic_center_explored:
        raise ValueError("Galactic Center has not been explored; council cannot vote")
    if state.current_resolution_id is None:
        raise ValueError("No active resolution to resolve")

    resolution = get_resolution(state.current_resolution_id)

    winning_side, side_a_totals, side_b_totals = tally_votes(state.ambassador_placements)

    # Determine winning players and their ambassador counts
    if winning_side == "side_a":
        winning_totals = side_a_totals
        winning_effect = {
            "effect_type": resolution.side_a_effect.effect_type,
            "params": resolution.side_a_effect.params,
        }
        winning_effect_desc = resolution.side_a_effect.description
    elif winning_side == "side_b":
        winning_totals = side_b_totals
        winning_effect = {
            "effect_type": resolution.side_b_effect.effect_type,
            "params": resolution.side_b_effect.params,
        }
        winning_effect_desc = resolution.side_b_effect.description
    else:
        winning_totals = {}
        winning_effect = {"effect_type": "none", "params": {}}
        winning_effect_desc = "Tie — no effect"

    winner_player_ids = [int(pid) for pid in winning_totals]

    # 1) Award 1 VP per ambassador on winning side to each winner
    new_vp_from_council = dict(state.vp_from_council)
    vp_awards: dict[str, int] = {}
    for pid_str, ambassador_count in winning_totals.items():
        player_id = int(pid_str)
        council_vp = ambassador_count  # 1 VP per ambassador

        result = await db.execute(select(Player).where(Player.id == player_id))
        player = result.scalar_one_or_none()
        if player is not None:
            player.vp_count += council_vp
            await db.flush()

        new_vp_from_council[pid_str] = new_vp_from_council.get(pid_str, 0) + council_vp
        vp_awards[pid_str] = council_vp

    state.vp_from_council = new_vp_from_council

    # 2) Apply resolution effect to winners
    await _apply_effect_to_winners(db, winning_effect, winner_player_ids)

    # 3) Record completion
    state.last_vote_round = current_round
    state.current_resolution_id = None
    state.ambassador_placements = {}

    await db.flush()

    return {
        "resolution_id": resolution.resolution_id,
        "resolution_name": resolution.name,
        "winning_side": winning_side,
        "winning_effect_description": winning_effect_desc,
        "side_a_total": sum(side_a_totals.values()),
        "side_b_total": sum(side_b_totals.values()),
        "vp_awards": vp_awards,
    }


# ---------------------------------------------------------------------------
# Upkeep integration helper
# ---------------------------------------------------------------------------


async def run_council_if_active(
    db: AsyncSession,
    game: Game,
    player_ids: list[int],
) -> dict | None:
    """Called from the turn engine during Upkeep.  If the Galactic Center has been
    explored and no vote has been run this round, start a new vote and immediately
    resolve it (AI/auto-placement: each player places all ambassadors on side_a by
    default in the base implementation; a real game would wait for player input).

    Returns the vote result dict, or None if the council is not yet active.

    NOTE: In a full implementation, the council vote would pause waiting for player
    placement decisions.  Here we auto-resolve in a single step so upkeep can
    complete atomically.  The /council endpoints allow human players to pre-place
    their ambassadors before upkeep triggers.
    """
    state = await get_council_state(db, game.id)
    if state is None or not state.galactic_center_explored:
        return None

    # Skip if vote already resolved this round
    if state.last_vote_round == game.current_round:
        return None

    # If no active resolution yet, start one
    if state.current_resolution_id is None:
        await start_new_vote(db, game.id)
        state = await get_council_state(db, game.id)

    # Auto-place any player who hasn't placed ambassadors (balanced: half on each side)
    for player_id in player_ids:
        pid = str(player_id)
        placed = state.ambassador_placements.get(pid, {})
        total_placed = placed.get("side_a", 0) + placed.get("side_b", 0)
        remaining = state.ambassadors_per_player - total_placed
        if remaining > 0:
            # Place half on side_a, half on side_b (auto)
            half_a = remaining // 2
            half_b = remaining - half_a
            if half_a > 0:
                await place_ambassadors(db, game.id, player_id, "side_a", half_a)
                # Reload state after mutation
                state = await get_council_state(db, game.id)
            if half_b > 0:
                await place_ambassadors(db, game.id, player_id, "side_b", half_b)
                state = await get_council_state(db, game.id)

    # Resolve the vote
    result = await resolve_vote(db, game.id, game.current_round)
    return result
