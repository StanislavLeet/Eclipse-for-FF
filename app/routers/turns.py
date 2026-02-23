from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.game import GameStatus
from app.models.user import User
from app.schemas.turn import ActionRequest, ActionResponse
from app.services.game_service import get_game, get_player_in_game
from app.services.turn_engine import advance_phase, get_game_actions, submit_action

router = APIRouter(prefix="/games", tags=["turns"])


async def _get_active_game_or_404(db: AsyncSession, game_id: int):
    game = await get_game(db, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    return game


@router.post(
    "/{game_id}/action",
    response_model=ActionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_player_action(
    game_id: int,
    body: ActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = await _get_active_game_or_404(db, game_id)
    if game.status != GameStatus.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Game is not active"
        )

    player = await get_player_in_game(db, game_id, current_user.id)
    if player is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You are not a player in this game"
        )

    try:
        action = await submit_action(db, game, player, body.action_type, body.payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return action


@router.get("/{game_id}/actions", response_model=list[ActionResponse])
async def get_action_history(
    game_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = await _get_active_game_or_404(db, game_id)
    if game.status == GameStatus.lobby:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Game has not started yet",
        )

    actions = await get_game_actions(db, game_id)
    return actions


@router.post("/{game_id}/advance-phase", response_model=dict)
async def advance_game_phase(
    game_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Advance a non-activation phase (combat/upkeep) to the next phase.
    Only the game host can call this."""
    game = await _get_active_game_or_404(db, game_id)
    if game.host_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the host can advance phases"
        )

    try:
        game = await advance_phase(db, game)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"current_phase": game.current_phase, "current_round": game.current_round}
