from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game, GamePhase, GameStatus
from app.models.game_action import ActionType, GameAction
from app.models.player import Player


async def get_active_player(db: AsyncSession, game_id: int) -> Player | None:
    result = await db.execute(
        select(Player).where(Player.game_id == game_id, Player.is_active_turn == True)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def get_players_for_game(db: AsyncSession, game_id: int) -> list[Player]:
    result = await db.execute(select(Player).where(Player.game_id == game_id))
    return list(result.scalars().all())


async def get_game_actions(db: AsyncSession, game_id: int) -> list[GameAction]:
    result = await db.execute(
        select(GameAction)
        .where(GameAction.game_id == game_id)
        .order_by(GameAction.timestamp)
    )
    return list(result.scalars().all())


async def initialize_turn_state(db: AsyncSession, game: Game) -> None:
    """Set up turn state when a game starts (called from game_service.start_game)."""
    result = await db.execute(select(Player).where(Player.game_id == game.id))
    players = list(result.scalars().all())

    # Sort by turn_order and mark the first player as active
    sorted_players = sorted(players, key=lambda p: p.turn_order if p.turn_order is not None else 0)
    for player in sorted_players:
        player.is_active_turn = False
        player.has_passed = False

    if sorted_players:
        sorted_players[0].is_active_turn = True

    game.current_phase = GamePhase.activation


async def validate_action(
    game: Game, player: Player, action_type: ActionType
) -> None:
    """Raise ValueError if the action is not legal given the current game state."""
    if game.status != GameStatus.active:
        raise ValueError("Game is not active")
    if game.current_phase != GamePhase.activation:
        raise ValueError(f"Actions can only be submitted during the activation phase, current phase: {game.current_phase}")
    if not player.is_active_turn:
        raise ValueError("It is not your turn")
    if player.has_passed:
        raise ValueError("You have already passed this round")


async def submit_action(
    db: AsyncSession,
    game: Game,
    player: Player,
    action_type: ActionType,
    payload: dict[str, Any] | None = None,
) -> GameAction:
    """Record an action, update turn state, and trigger phase transitions if needed."""
    await validate_action(game, player, action_type)

    action = GameAction(
        game_id=game.id,
        player_id=player.id,
        action_type=action_type,
        payload=payload,
        round_number=game.current_round,
    )
    db.add(action)

    if action_type == ActionType.pass_action:
        player.has_passed = True

    await _advance_turn(db, game, player)

    await db.commit()
    await db.refresh(action)
    return action


async def _advance_turn(db: AsyncSession, game: Game, current_player: Player) -> None:
    """Move active turn to the next eligible player, or transition the phase."""
    result = await db.execute(select(Player).where(Player.game_id == game.id))
    players = list(result.scalars().all())
    sorted_players = sorted(
        players, key=lambda p: p.turn_order if p.turn_order is not None else 0
    )

    # If all players have passed (including the current player who just passed), transition
    all_passed = all(p.has_passed for p in sorted_players)
    if all_passed:
        current_player.is_active_turn = False
        await _transition_phase(db, game, sorted_players)
        return

    # Find the next player who hasn't passed
    current_idx = next(
        (i for i, p in enumerate(sorted_players) if p.id == current_player.id), 0
    )
    n = len(sorted_players)
    current_player.is_active_turn = False

    for offset in range(1, n + 1):
        next_idx = (current_idx + offset) % n
        next_player = sorted_players[next_idx]
        if not next_player.has_passed:
            next_player.is_active_turn = True
            return


async def _transition_phase(
    db: AsyncSession, game: Game, players: list[Player]
) -> None:
    """Advance the game to the next phase."""
    if game.current_phase == GamePhase.activation:
        game.current_phase = GamePhase.combat
    elif game.current_phase == GamePhase.combat:
        game.current_phase = GamePhase.upkeep
    elif game.current_phase == GamePhase.upkeep:
        # Start a new round
        game.current_round += 1
        game.current_phase = GamePhase.activation

        # Reset all players for the new round
        for p in players:
            p.has_passed = False
            p.is_active_turn = False

        # First player becomes active
        first_player = min(
            players, key=lambda p: p.turn_order if p.turn_order is not None else 0
        )
        first_player.is_active_turn = True


async def advance_phase(db: AsyncSession, game: Game) -> Game:
    """Manually advance the game phase (used for combat/upkeep phases that have no actions)."""
    if game.status != GameStatus.active:
        raise ValueError("Game is not active")
    if game.current_phase == GamePhase.activation:
        raise ValueError("Activation phase ends when all players pass")

    result = await db.execute(select(Player).where(Player.game_id == game.id))
    players = list(result.scalars().all())
    await _transition_phase(db, game, players)
    await db.commit()
    await db.refresh(game)
    return game
