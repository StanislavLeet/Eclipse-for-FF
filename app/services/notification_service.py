"""Notification service: composes and dispatches emails for game events."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.game import Game
from app.models.player import Player
from app.models.user import User
from app.tasks.email_sender import send_email

logger = logging.getLogger(__name__)


async def _get_user_email(db: AsyncSession, user_id: int) -> str | None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    return user.email if user else None


def _game_link(game: Game) -> str:
    return f"{settings.base_url}/games/{game.id}"


async def notify_turn_change(db: AsyncSession, game: Game, next_player: Player) -> None:
    """Send an email to the player whose turn it now is.

    Includes the game name, current round, current phase, and a direct link.
    """
    email = await _get_user_email(db, next_player.user_id)
    if not email:
        logger.warning("No email found for player %s (user_id=%s)", next_player.id, next_player.user_id)
        return

    phase = game.current_phase.value if game.current_phase else "activation"
    subject = f"Eclipse: It's your turn in '{game.name}'"
    body = (
        f"Hello!\n\n"
        f"It's your turn in the game '{game.name}'.\n"
        f"Round: {game.current_round}\n"
        f"Phase: {phase}\n\n"
        f"Click here to play: {_game_link(game)}\n\n"
        f"Good luck!\n"
    )
    await send_email(email, subject, body)


async def notify_game_started(db: AsyncSession, game: Game, players: list[Player]) -> None:
    """Send an email to every player announcing that the game has started."""
    game_link = _game_link(game)
    subject = f"Eclipse: Game '{game.name}' has started!"

    for player in players:
        email = await _get_user_email(db, player.user_id)
        if not email:
            continue

        species_name = player.species.value if player.species else "Unknown"
        body = (
            f"Hello!\n\n"
            f"The game '{game.name}' has started!\n"
            f"You are playing as: {species_name}\n\n"
            f"Click here to play: {game_link}\n\n"
            f"Good luck!\n"
        )
        await send_email(email, subject, body)


async def notify_game_ended(
    db: AsyncSession,
    game: Game,
    players: list[Player],
    winner: Player | None = None,
) -> None:
    """Send an email to every player announcing the game result."""
    game_link = _game_link(game)
    subject = f"Eclipse: Game '{game.name}' has ended!"

    winner_line = ""
    if winner:
        winner_line = f"Winner: Player {winner.id} with {winner.vp_count} VP\n"

    scores = "\n".join(f"  Player {p.id}: {p.vp_count} VP" for p in players)

    for player in players:
        email = await _get_user_email(db, player.user_id)
        if not email:
            continue

        body = (
            f"Hello!\n\n"
            f"The game '{game.name}' has ended!\n"
            f"{winner_line}"
            f"\nFinal scores:\n{scores}\n\n"
            f"Click here to view results: {game_link}\n"
        )
        await send_email(email, subject, body)
