from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.species import list_species
from app.database import get_db
from app.dependencies import get_current_user
from app.models.game import GameStatus
from app.models.user import User
from app.schemas.game import (
    GameCreate,
    GameResponse,
    InviteCreate,
    InviteResponse,
    JoinGame,
    PlayerResponse,
    SelectSpecies,
    SpeciesInfo,
)
from app.services.game_service import (
    create_game,
    create_invite,
    get_game,
    get_players_for_game,
    join_game,
    select_species,
    start_game,
)

router = APIRouter(prefix="/games", tags=["games"])


def _game_response(game, players) -> GameResponse:
    return GameResponse(
        id=game.id,
        name=game.name,
        status=game.status,
        current_round=game.current_round,
        current_phase=game.current_phase,
        max_players=game.max_players,
        host_user_id=game.host_user_id,
        created_at=game.created_at,
        players=[PlayerResponse.model_validate(p) for p in players],
    )


async def _get_game_or_404(db: AsyncSession, game_id: int):
    game = await get_game(db, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    return game


@router.get("/species", response_model=list[SpeciesInfo])
async def get_species():
    return [
        SpeciesInfo(
            species_id=s.species_id.value,
            name=s.name,
            description=s.description,
            starting_money=s.starting_money,
            starting_science=s.starting_science,
            starting_materials=s.starting_materials,
            homeworld_slots=s.homeworld_slots,
            starting_ships=s.starting_ships,
            special_ability=s.special_ability,
        )
        for s in list_species()
    ]


@router.post("", response_model=GameResponse, status_code=status.HTTP_201_CREATED)
async def create_new_game(
    body: GameCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = await create_game(db, name=body.name, max_players=body.max_players, host=current_user)
    players = await get_players_for_game(db, game.id)
    return _game_response(game, players)


@router.get("/{game_id}", response_model=GameResponse)
async def get_game_info(
    game_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = await _get_game_or_404(db, game_id)
    players = await get_players_for_game(db, game.id)
    return _game_response(game, players)


@router.post("/{game_id}/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def invite_player(
    game_id: int,
    body: InviteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = await _get_game_or_404(db, game_id)
    if game.host_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the host can send invites")
    if game.status != GameStatus.lobby:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Game is not in lobby")
    invite = await create_invite(db, game_id=game.id, invitee_email=str(body.invitee_email))
    return invite


@router.post("/{game_id}/join", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
async def join_game_endpoint(
    game_id: int,
    body: JoinGame,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = await _get_game_or_404(db, game_id)
    if game.status != GameStatus.lobby:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Game is not in lobby")
    try:
        player = await join_game(db, game=game, user=current_user, token=body.token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return player


@router.post("/{game_id}/select-species", response_model=PlayerResponse)
async def select_player_species(
    game_id: int,
    body: SelectSpecies,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = await _get_game_or_404(db, game_id)
    if game.status != GameStatus.lobby:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Game is not in lobby")
    try:
        player = await select_species(db, game=game, user=current_user, species=body.species)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return player


@router.post("/{game_id}/start", response_model=GameResponse)
async def start_game_endpoint(
    game_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = await _get_game_or_404(db, game_id)
    if game.status != GameStatus.lobby:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Game is already started")
    try:
        game = await start_game(db, game=game, user=current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    players = await get_players_for_game(db, game.id)
    return _game_response(game, players)
