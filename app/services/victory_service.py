"""Victory service for Eclipse: Second Dawn.

Handles end-of-game VP calculation, winner determination, and game finalization.

VP sources:
  - Ongoing VP (accumulated during play): combat kills, council votes, discovery tiles
  - Colony control (at game end): 1 VP per controlled hex system
  - Tech VP (at game end): effects with effect_type="vp" and trigger="game_end"

Tiebreaker: most money (from PlayerResources) wins ties.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.technologies import get_technology
from app.models.game import Game, GameStatus
from app.models.hex_tile import HexTile
from app.models.player import Player
from app.models.player_resources import PlayerResources
from app.models.player_technology import PlayerTechnology


# ---------------------------------------------------------------------------
# VP calculation helpers
# ---------------------------------------------------------------------------


async def calculate_colony_vp(db: AsyncSession, player_id: int, game_id: int) -> int:
    """Count hex tiles owned by the player (1 VP per controlled system)."""
    result = await db.execute(
        select(HexTile).where(
            HexTile.game_id == game_id,
            HexTile.owner_player_id == player_id,
        )
    )
    tiles = list(result.scalars().all())
    return len(tiles)


async def calculate_tech_vp(db: AsyncSession, player_id: int) -> int:
    """Sum VP from technologies with a 'vp' effect triggered at game_end (e.g., Monolith)."""
    result = await db.execute(
        select(PlayerTechnology).where(PlayerTechnology.player_id == player_id)
    )
    owned_techs = list(result.scalars().all())
    total = 0
    for pt in owned_techs:
        try:
            tech = get_technology(pt.tech_id)
        except KeyError:
            continue
        for effect in tech.effects:
            if effect.effect_type == "vp" and effect.params.get("trigger") == "game_end":
                total += effect.params.get("vp", 0)
    return total


# ---------------------------------------------------------------------------
# Final tally
# ---------------------------------------------------------------------------


async def calculate_final_vp(db: AsyncSession, game: Game) -> list[Player]:
    """Compute all end-of-game VP for every player.

    Updates each player's vp_count and vp_breakdown in the DB.
    Returns the updated player list sorted by final VP (descending).
    """
    result = await db.execute(select(Player).where(Player.game_id == game.id))
    players = list(result.scalars().all())

    for player in players:
        ongoing_vp = player.vp_count  # VP accumulated during the game

        colony_vp = await calculate_colony_vp(db, player.id, game.id)
        tech_vp = await calculate_tech_vp(db, player.id)

        total_vp = ongoing_vp + colony_vp + tech_vp
        player.vp_count = total_vp
        player.vp_breakdown = {
            "ongoing": ongoing_vp,
            "colony": colony_vp,
            "tech": tech_vp,
            "total": total_vp,
        }

    await db.flush()

    # Return sorted by VP descending
    return sorted(players, key=lambda p: p.vp_count, reverse=True)


# ---------------------------------------------------------------------------
# Winner determination
# ---------------------------------------------------------------------------


async def determine_winner(
    db: AsyncSession,
    players: list[Player],
) -> Player | None:
    """Return the winning player after final VP calculation.

    Tiebreaker: most money (from PlayerResources).
    Returns None if there are no players.
    """
    if not players:
        return None

    max_vp = max(p.vp_count for p in players)
    contenders = [p for p in players if p.vp_count == max_vp]

    if len(contenders) == 1:
        return contenders[0]

    # Tiebreaker: most money
    best_money = -1
    winner = contenders[0]
    for player in contenders:
        res_result = await db.execute(
            select(PlayerResources).where(PlayerResources.player_id == player.id)
        )
        resources = res_result.scalar_one_or_none()
        money = resources.money if resources else 0
        if money > best_money:
            best_money = money
            winner = player

    return winner


# ---------------------------------------------------------------------------
# Game finalization
# ---------------------------------------------------------------------------


async def finalize_game(db: AsyncSession, game: Game) -> Player | None:
    """Finalize the game: compute final VP, mark as finished, send emails.

    Returns the winning Player (or None if no players).
    """
    # Compute and update final VP
    sorted_players = await calculate_final_vp(db, game)

    # Determine winner with tiebreaker
    winner = await determine_winner(db, sorted_players)

    # Mark the game as finished
    game.status = GameStatus.finished

    await db.flush()

    # Send end-game notifications (best-effort)
    try:
        from app.services.notification_service import notify_game_ended
        await notify_game_ended(db, game, sorted_players, winner)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Failed to send game-end notifications")

    return winner


# ---------------------------------------------------------------------------
# Scores endpoint helper
# ---------------------------------------------------------------------------


async def get_scores(db: AsyncSession, game_id: int) -> list[dict]:
    """Return current VP standings for all players.

    For finished games, vp_breakdown contains the final detailed breakdown.
    For active games, shows the current running vp_count with no breakdown.
    Sorted by VP descending.
    """
    result = await db.execute(select(Player).where(Player.game_id == game_id))
    players = sorted(result.scalars().all(), key=lambda p: p.vp_count, reverse=True)

    standings = []
    for player in players:
        standings.append(
            {
                "player_id": player.id,
                "user_id": player.user_id,
                "species": player.species.value if player.species else None,
                "vp_count": player.vp_count,
                "vp_breakdown": player.vp_breakdown,
            }
        )
    return standings
