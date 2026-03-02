"""Research router — GET /games/{game_id}/players/{player_id}/technologies."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.game import GameStatus
from app.models.user import User
from app.schemas.research import (
    PlayerTechnologyResponse,
    TechnologyDefinitionResponse,
)
from app.services.game_service import get_game, get_player_in_game, get_players_for_game
from app.services.research_service import (
    calculate_effective_cost,
    count_techs_in_category,
    get_player_technologies,
)
from app.data.technologies import get_technology, list_technologies

router = APIRouter(prefix="/games", tags=["research"])


@router.get(
    "/{game_id}/players/{player_id}/technologies",
    response_model=list[PlayerTechnologyResponse],
)
async def get_player_technologies_endpoint(
    game_id: int,
    player_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all technologies acquired by a player, enriched with tech metadata."""
    game = await get_game(db, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    if game.status == GameStatus.lobby:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Game has not started yet"
        )

    requester = await get_player_in_game(db, game_id, current_user.id)
    if requester is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You are not a player in this game"
        )

    players = await get_players_for_game(db, game_id)
    player = next((p for p in players if p.id == player_id), None)
    if player is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found in this game",
        )

    records = await get_player_technologies(player_id, db)
    result = []
    for rec in records:
        try:
            tech = get_technology(rec.tech_id)
        except KeyError:
            # Tech definition missing — skip gracefully
            continue
        result.append(
            PlayerTechnologyResponse(
                id=rec.id,
                player_id=rec.player_id,
                tech_id=rec.tech_id,
                tech_name=tech.name,
                category=tech.category,
                acquired_round=rec.acquired_round,
                acquired_at=rec.acquired_at,
                effects=[
                    {"effect_type": e.effect_type, "params": e.params, "description": e.description}
                    for e in tech.effects
                ],
            )
        )
    return result


@router.get(
    "/{game_id}/players/{player_id}/technologies/available",
    response_model=list[TechnologyDefinitionResponse],
)
async def get_available_technologies_endpoint(
    game_id: int,
    player_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all technologies available for the player to research, with effective costs."""
    game = await get_game(db, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    if game.status == GameStatus.lobby:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Game has not started yet"
        )

    requester = await get_player_in_game(db, game_id, current_user.id)
    if requester is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You are not a player in this game"
        )

    players = await get_players_for_game(db, game_id)
    player = next((p for p in players if p.id == player_id), None)
    if player is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found in this game",
        )

    from app.services.research_service import get_player_tech_ids
    owned_ids = await get_player_tech_ids(player_id, db)

    result = []
    for tech in list_technologies():
        if not tech.can_research:
            continue
        if tech.tech_id in owned_ids:
            continue
        # Check prerequisites
        prereqs_met = all(p in owned_ids for p in tech.prerequisites)
        if not prereqs_met:
            continue
        owned_count = await count_techs_in_category(player_id, tech.category, db)
        effective_cost = calculate_effective_cost(tech, owned_count)
        result.append(
            TechnologyDefinitionResponse(
                tech_id=tech.tech_id,
                name=tech.name,
                category=tech.category,
                base_cost=tech.base_cost,
                effective_cost=effective_cost,
                prerequisites=tech.prerequisites,
                can_research=tech.can_research,
                effects=[
                    {"effect_type": e.effect_type, "params": e.params, "description": e.description}
                    for e in tech.effects
                ],
                flavor_text=tech.flavor_text,
            )
        )
    return result
