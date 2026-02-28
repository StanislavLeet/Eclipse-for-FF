"""Combat router — endpoints for combat logs and retreat actions."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.game import GamePhase, GameStatus
from app.models.user import User
from app.services.combat_service import get_combat_logs, retreat_ship
from app.services.game_service import get_game, get_player_in_game

router = APIRouter(prefix="/games", tags=["combat"])


@router.get("/{game_id}/combat/logs")
async def get_combat_logs_endpoint(
    game_id: int,
    round: int | None = Query(default=None, description="Filter by game round"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all combat logs for a game, optionally filtered by round."""
    game = await get_game(db, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    if game.status == GameStatus.lobby:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Game has not started yet",
        )

    logs = await get_combat_logs(game_id, db, round_number=round)
    return [
        {
            "id": log.id,
            "game_id": log.game_id,
            "hex_tile_id": log.hex_tile_id,
            "round_number": log.round_number,
            "attacker_id": log.attacker_id,
            "log_entries": log.log_entries,
        }
        for log in logs
    ]


@router.post("/{game_id}/combat/retreat", status_code=status.HTTP_200_OK)
async def retreat_ship_endpoint(
    game_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retreat a ship to an adjacent hex before combat resolves.

    Body: {"ship_id": int, "target_hex_id": int}
    Only valid during the combat phase.
    """
    game = await get_game(db, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    if game.status != GameStatus.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Game is not active"
        )
    if game.current_phase != GamePhase.combat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Retreat is only allowed during the combat phase",
        )

    player = await get_player_in_game(db, game_id, current_user.id)
    if player is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a player in this game",
        )

    ship_id = body.get("ship_id")
    target_hex_id = body.get("target_hex_id")
    if ship_id is None or target_hex_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Body must contain 'ship_id' and 'target_hex_id'",
        )

    try:
        ship = await retreat_ship(
            game_id=game_id,
            player_id=player.id,
            ship_id=ship_id,
            target_hex_id=target_hex_id,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await db.commit()
    return {
        "ship_id": ship.id,
        "new_hex_tile_id": ship.hex_tile_id,
        "message": "Ship retreated successfully",
    }
