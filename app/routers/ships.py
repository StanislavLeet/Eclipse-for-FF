"""Ships router — endpoints for ship blueprints and ship listings."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.game import GameStatus
from app.models.user import User
from app.services.game_service import get_game, get_player_in_game, get_players_for_game
from app.services.ship_service import (
    get_blueprints_for_player,
    get_ships_for_player,
)
from app.data.ship_parts import get_component, get_ship_type, compute_power_balance

router = APIRouter(prefix="/games", tags=["ships"])


@router.get("/{game_id}/players/{player_id}/blueprints")
async def get_player_blueprints(
    game_id: int,
    player_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all ship blueprints for a player, enriched with power balance stats."""
    game = await get_game(db, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    if game.status == GameStatus.lobby:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Game has not started yet",
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

    blueprints = await get_blueprints_for_player(player_id, db)
    result = []
    for bp in blueprints:
        power_balance = compute_power_balance(bp.slots)
        slot_details = []
        for component_id in bp.slots:
            if component_id is None:
                slot_details.append(None)
            else:
                try:
                    comp = get_component(component_id)
                    slot_details.append({
                        "component_id": comp.component_id,
                        "name": comp.name,
                        "category": comp.category,
                        "power_generated": comp.power_generated,
                        "power_consumed": comp.power_consumed,
                        "damage": comp.damage,
                        "movement": comp.movement,
                        "accuracy": comp.accuracy,
                        "shield": comp.shield,
                        "extra_hp": comp.extra_hp,
                        "fires_first": comp.fires_first,
                        "requires_tech": comp.requires_tech,
                    })
                except KeyError:
                    slot_details.append({"component_id": component_id, "error": "unknown"})

        try:
            st = get_ship_type(bp.ship_type)
            ship_type_info = {
                "ship_type_id": st.ship_type_id,
                "name": st.name,
                "slot_count": st.slot_count,
                "base_hp": st.base_hp,
                "base_initiative": st.base_initiative,
                "can_move": st.can_move,
                "build_cost": st.build_cost,
            }
        except KeyError:
            ship_type_info = {"ship_type_id": bp.ship_type}

        result.append({
            "id": bp.id,
            "player_id": bp.player_id,
            "ship_type": bp.ship_type,
            "slots": slot_details,
            "is_valid": bp.is_valid,
            "power_balance": power_balance,
            "ship_type_info": ship_type_info,
        })
    return result


@router.get("/{game_id}/players/{player_id}/ships")
async def get_player_ships(
    game_id: int,
    player_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all ships belonging to a player in the game."""
    game = await get_game(db, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    if game.status == GameStatus.lobby:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Game has not started yet",
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

    ships = await get_ships_for_player(player_id, game_id, db)
    return [
        {
            "id": s.id,
            "game_id": s.game_id,
            "player_id": s.player_id,
            "ship_type": s.ship_type,
            "hex_tile_id": s.hex_tile_id,
            "hp_remaining": s.hp_remaining,
            "is_ancient": s.is_ancient,
        }
        for s in ships
    ]
