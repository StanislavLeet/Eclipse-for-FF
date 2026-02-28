import random

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.species import list_species
from app.database import get_db
from app.dependencies import get_current_user
from app.models.game import GameStatus
from app.models.player import Species
from app.models.user import User
from app.schemas.game import (
    GameCreate,
    GameDeletionStatusResponse,
    GameResponse,
    GameStatusResponse,
    HexTileResponse,
    InviteCreate,
    InviteResponse,
    JoinGame,
    PlayerResponse,
    PlayerScoreResponse,
    ScoresResponse,
    SelectSpecies,
    ShipOnTileResponse,
    SpeciesInfo,
    SystemResponse,
)
from app.services.game_service import (
    approve_game_deletion,
    create_game,
    create_invite,
    get_game,
    get_game_deletion_approvals,
    get_game_deletion_request,
    get_players_for_game,
    list_games_for_user,
    join_game,
    request_or_approve_game_deletion,
    select_species,
    start_game,
)
from app.services.map_generator import get_map_tiles, get_system_for_tile
from app.services.ship_service import get_ships_for_tile

router = APIRouter(prefix="/games", tags=["games"])



async def _build_deletion_status(
    db: AsyncSession, game_id: int, current_user_id: int
) -> GameDeletionStatusResponse | None:
    request = await get_game_deletion_request(db, game_id)
    if request is None:
        return None

    approvals = await get_game_deletion_approvals(db, request.id)
    pending = sum(1 for approval in approvals if not approval.approved)
    current = next((approval for approval in approvals if approval.user_id == current_user_id), None)

    return GameDeletionStatusResponse(
        request_id=request.id,
        status=request.status.value,
        requested_by_user_id=request.requested_by_user_id,
        pending_approvals=pending,
        is_current_user_approved=bool(current and current.approved),
        can_current_user_approve=current is not None and not current.approved,
    )


async def _game_response_for_user(db: AsyncSession, game, players, current_user_id: int) -> GameResponse:
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
        deletion_status=await _build_deletion_status(db, game.id, current_user_id),
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




@router.get("", response_model=list[GameResponse])
async def list_games(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    games = await list_games_for_user(db, current_user.id)
    responses: list[GameResponse] = []
    for game in games:
        players = await get_players_for_game(db, game.id)
        responses.append(await _game_response_for_user(db, game, players, current_user.id))
    return responses

@router.post("", response_model=GameResponse, status_code=status.HTTP_201_CREATED)
async def create_new_game(
    body: GameCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = await create_game(db, name=body.name, max_players=body.max_players, host=current_user)
    players = await get_players_for_game(db, game.id)
    return await _game_response_for_user(db, game, players, current_user.id)


@router.get("/{game_id}", response_model=GameResponse)
async def get_game_info(
    game_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = await _get_game_or_404(db, game_id)
    players = await get_players_for_game(db, game.id)
    return await _game_response_for_user(db, game, players, current_user.id)


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
    players = await get_players_for_game(db, game.id)
    requested_species = body.species
    if requested_species == "random":
        taken_species = {
            p.species
            for p in players
            if p.species is not None and p.species != Species.human
        }
        available_species = [
            species for species in Species if species not in taken_species
        ]
        if not available_species:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No species available for random selection",
            )
        species = random.choice(available_species)
    else:
        species = Species(requested_species)

    try:
        player = await select_species(db, game=game, user=current_user, species=species)
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
    return await _game_response_for_user(db, game, players, current_user.id)




@router.delete("/{game_id}")
async def request_delete_game(
    game_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = await _get_game_or_404(db, game_id)

    if game.status == GameStatus.lobby:
        if game.host_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only host can delete lobby game")
        request, deleted = await request_or_approve_game_deletion(db, game=game, user=current_user)
        if deleted:
            return {"detail": "Game deleted"}
        return {"detail": "Deletion request created", "request_id": request.id}

    try:
        request, deleted = await request_or_approve_game_deletion(db, game=game, user=current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if deleted:
        return {"detail": "Game deleted"}
    return {"detail": "Deletion request sent to players", "request_id": request.id}


@router.post("/{game_id}/delete/approve")
async def approve_delete_game(
    game_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = await _get_game_or_404(db, game_id)
    try:
        request, deleted = await approve_game_deletion(db, game=game, user=current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if deleted:
        return {"detail": "Game deleted"}
    return {"detail": "Deletion approved", "request_id": request.id}


@router.get("/{game_id}/status", response_model=GameStatusResponse)
async def get_game_status(
    game_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a lightweight game status summary for polling."""
    game = await _get_game_or_404(db, game_id)
    players = await get_players_for_game(db, game.id)
    active_player = next((p for p in players if p.is_active_turn), None)
    return GameStatusResponse(
        id=game.id,
        name=game.name,
        status=game.status,
        current_round=game.current_round,
        current_phase=game.current_phase,
        active_player_id=active_player.id if active_player else None,
    )


@router.get("/{game_id}/map", response_model=list[HexTileResponse])
async def get_game_map(
    game_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = await _get_game_or_404(db, game_id)
    if game.status == GameStatus.lobby:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Map is not available until the game has started",
        )
    tiles = await get_map_tiles(db, game_id)
    result: list[HexTileResponse] = []
    for tile in tiles:
        system = await get_system_for_tile(db, tile.id)
        system_resp: SystemResponse | None = None
        if system is not None:
            system_resp = SystemResponse.model_validate(system)
        ships = await get_ships_for_tile(tile.id, db)
        ships_resp = [ShipOnTileResponse.model_validate(s) for s in ships]
        result.append(
            HexTileResponse(
                id=tile.id,
                game_id=tile.game_id,
                q=tile.q,
                r=tile.r,
                tile_type=tile.tile_type,
                tile_template_id=tile.tile_template_id,
                rotation=tile.rotation,
                is_explored=tile.is_explored,
                owner_player_id=tile.owner_player_id,
                system=system_resp,
                ships=ships_resp,
            )
        )
    return result


@router.get("/{game_id}/scores", response_model=ScoresResponse)
async def get_game_scores(
    game_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return current VP standings for all players in the game.

    Available during active and finished games.
    For finished games, vp_breakdown contains the full per-source breakdown.
    """
    game = await _get_game_or_404(db, game_id)
    if game.status == GameStatus.lobby:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scores are not available until the game has started",
        )
    from app.services.victory_service import get_scores
    standings = await get_scores(db, game_id)

    # Determine winner_player_id for finished games
    winner_player_id: int | None = None
    if game.status == GameStatus.finished and standings:
        winner_player_id = standings[0]["player_id"]

    player_scores = [
        PlayerScoreResponse(
            player_id=s["player_id"],
            user_id=s["user_id"],
            species=s["species"],
            vp_count=s["vp_count"],
            vp_breakdown=s["vp_breakdown"],
        )
        for s in standings
    ]
    return ScoresResponse(
        game_id=game_id,
        game_status=game.status,
        winner_player_id=winner_player_id,
        players=player_scores,
    )
