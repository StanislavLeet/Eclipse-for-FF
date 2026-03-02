"""Galactic Council router — endpoints for ambassador placement and voting."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.game import GameStatus
from app.models.user import User
from app.data.resolutions import list_resolutions
from app.services.council_service import (
    get_or_create_council_state,
    mark_galactic_center_explored,
    place_ambassadors,
    resolve_vote,
    start_new_vote,
    tally_votes,
)
from app.services.game_service import get_game, get_player_in_game

router = APIRouter(prefix="/games", tags=["council"])

# Separate router for non-game-scoped council endpoints (avoids /games/{game_id} conflict)
council_meta_router = APIRouter(prefix="/council", tags=["council"])


@council_meta_router.get("/resolutions")
async def list_resolutions_meta_endpoint(
    current_user: User = Depends(get_current_user),
):
    """Return all available resolution cards."""
    return [
        {
            "resolution_id": r.resolution_id,
            "name": r.name,
            "category": r.category,
            "side_a_name": r.side_a_name,
            "side_a_effect": {
                "effect_type": r.side_a_effect.effect_type,
                "params": r.side_a_effect.params,
                "description": r.side_a_effect.description,
            },
            "side_b_name": r.side_b_name,
            "side_b_effect": {
                "effect_type": r.side_b_effect.effect_type,
                "params": r.side_b_effect.params,
                "description": r.side_b_effect.description,
            },
            "flavor_text": r.flavor_text,
        }
        for r in list_resolutions()
    ]


@router.get("/{game_id}/council")
async def get_council_state_endpoint(
    game_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current council state for the game."""
    game = await get_game(db, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")

    requester = await get_player_in_game(db, game_id, current_user.id)
    if requester is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You are not a player in this game"
        )

    council = await get_or_create_council_state(db, game_id)
    await db.commit()

    placements = council.ambassador_placements
    winning_side, side_a_totals, side_b_totals = tally_votes(placements)

    return {
        "game_id": game_id,
        "galactic_center_explored": council.galactic_center_explored,
        "current_resolution_id": council.current_resolution_id,
        "ambassador_placements": council.ambassador_placements,
        "vp_from_council": council.vp_from_council,
        "ambassadors_per_player": council.ambassadors_per_player,
        "last_vote_round": council.last_vote_round,
        "current_tally": {
            "side_a": sum(side_a_totals.values()),
            "side_b": sum(side_b_totals.values()),
            "leading": winning_side,
        },
    }


@router.post("/{game_id}/council/explore-center", status_code=status.HTTP_200_OK)
async def mark_galactic_center_explored_endpoint(
    game_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark the Galactic Center as explored, enabling council votes.

    This is normally triggered automatically by the exploration service.
    This endpoint allows manual triggering (e.g. game master / testing).
    """
    game = await get_game(db, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    if game.status != GameStatus.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Game is not active"
        )

    player = await get_player_in_game(db, game_id, current_user.id)
    if player is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a player in this game",
        )

    council = await mark_galactic_center_explored(db, game_id)
    await db.commit()
    return {
        "game_id": game_id,
        "galactic_center_explored": council.galactic_center_explored,
        "message": "Galactic Center marked as explored; council will convene next Upkeep",
    }


@router.post("/{game_id}/council/start-vote", status_code=status.HTTP_200_OK)
async def start_vote_endpoint(
    game_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a new council vote (optionally specifying a resolution_id).

    Body: {"resolution_id": str}  (optional)
    """
    game = await get_game(db, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    if game.status != GameStatus.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Game is not active"
        )

    player = await get_player_in_game(db, game_id, current_user.id)
    if player is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a player in this game",
        )

    resolution_id = body.get("resolution_id")  # may be None → random selection

    try:
        council = await start_new_vote(db, game_id, resolution_id)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await db.commit()
    return {
        "game_id": game_id,
        "current_resolution_id": council.current_resolution_id,
        "message": "New council vote started",
    }


@router.post("/{game_id}/council/place-ambassadors", status_code=status.HTTP_200_OK)
async def place_ambassadors_endpoint(
    game_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Place ambassador tokens on a resolution side.

    Body: {"side": "side_a" | "side_b", "count": int}
    """
    game = await get_game(db, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    if game.status != GameStatus.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Game is not active"
        )

    player = await get_player_in_game(db, game_id, current_user.id)
    if player is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a player in this game",
        )

    side = body.get("side")
    count = body.get("count", 1)

    if not side:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Body must contain 'side' ('side_a' or 'side_b')",
        )

    try:
        council = await place_ambassadors(db, game_id, player.id, side, int(count))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await db.commit()

    pid = str(player.id)
    placements = council.ambassador_placements.get(pid, {})
    return {
        "game_id": game_id,
        "player_id": player.id,
        "side_a_placed": placements.get("side_a", 0),
        "side_b_placed": placements.get("side_b", 0),
        "ambassadors_remaining": council.ambassadors_per_player - placements.get("side_a", 0) - placements.get("side_b", 0),
        "message": f"Placed {count} ambassador(s) on {side}",
    }


@router.post("/{game_id}/council/resolve", status_code=status.HTTP_200_OK)
async def resolve_vote_endpoint(
    game_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resolve the active council vote, apply effects, and award VP.

    In normal play this is triggered automatically during the Upkeep phase.
    This endpoint allows manual resolution (game master / testing).
    """
    game = await get_game(db, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    if game.status != GameStatus.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Game is not active"
        )

    player = await get_player_in_game(db, game_id, current_user.id)
    if player is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a player in this game",
        )

    try:
        result = await resolve_vote(db, game_id, game.current_round)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await db.commit()
    return result
