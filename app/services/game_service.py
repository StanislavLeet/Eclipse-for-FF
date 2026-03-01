import secrets

from datetime import datetime, timezone

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game, GameStatus
from app.models.game_action import GameAction
from app.models.game_deletion import GameDeletionApproval, GameDeletionRequest, GameDeletionRequestStatus
from app.models.game_invite import GameInvite
from app.models.player import Player, Species
from app.models.user import User
from app.services.exploration_service import initialize_discovery_deck
from app.services.map_generator import generate_map
from app.services.resource_service import create_player_resources
from app.services.turn_engine import initialize_turn_state
from app.services.ship_service import initialize_blueprints, place_starting_ships


async def create_game(db: AsyncSession, name: str, max_players: int, host: User) -> Game:
    game = Game(
        name=name,
        max_players=max_players,
        host_user_id=host.id,
        status=GameStatus.lobby,
        current_round=0,
    )
    db.add(game)
    await db.flush()  # get game.id before adding player

    # Host automatically joins as the first player
    player = Player(game_id=game.id, user_id=host.id, turn_order=0)
    db.add(player)
    await db.commit()
    await db.refresh(game)
    return game


async def get_game(db: AsyncSession, game_id: int) -> Game | None:
    result = await db.execute(select(Game).where(Game.id == game_id))
    return result.scalar_one_or_none()


async def list_games_for_user(db: AsyncSession, user_id: int) -> list[Game]:
    result = await db.execute(
        select(Game)
        .outerjoin(Player, Player.game_id == Game.id)
        .where(or_(Game.status == GameStatus.lobby, Player.user_id == user_id))
        .order_by(Game.created_at.desc())
    )
    return list(result.scalars().unique().all())


async def get_players_for_game(db: AsyncSession, game_id: int) -> list[Player]:
    result = await db.execute(select(Player).where(Player.game_id == game_id))
    return list(result.scalars().all())


async def get_player_in_game(db: AsyncSession, game_id: int, user_id: int) -> Player | None:
    result = await db.execute(
        select(Player).where(Player.game_id == game_id, Player.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_invite(
    db: AsyncSession, game_id: int, invitee_email: str
) -> GameInvite:
    token = secrets.token_urlsafe(32)
    invite = GameInvite(game_id=game_id, invitee_email=invitee_email, token=token)
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


async def get_invite_by_token(db: AsyncSession, token: str) -> GameInvite | None:
    result = await db.execute(select(GameInvite).where(GameInvite.token == token))
    return result.scalar_one_or_none()


async def join_game(db: AsyncSession, game: Game, user: User, token: str | None = None) -> Player:
    existing = await get_player_in_game(db, game.id, user.id)
    if existing is not None:
        raise ValueError("Already joined this game")

    if token is not None:
        invite = await get_invite_by_token(db, token)
        if invite is None or invite.game_id != game.id:
            raise ValueError("Invalid invite token")
        if invite.accepted:
            raise ValueError("Invite already used")
        invite.accepted = True

    players = await get_players_for_game(db, game.id)
    if len(players) >= game.max_players:
        raise ValueError("Game is full")

    turn_order = len(players)
    player = Player(game_id=game.id, user_id=user.id, turn_order=turn_order)
    db.add(player)
    await db.commit()
    await db.refresh(player)
    return player


async def select_species(
    db: AsyncSession, game: Game, user: User, species: Species
) -> Player:
    player = await get_player_in_game(db, game.id, user.id)
    if player is None:
        raise ValueError("Not a player in this game")

    # Check no other player has already chosen this species.
    # Human is intentionally allowed to be picked by multiple players.
    players = await get_players_for_game(db, game.id)
    for p in players:
        if (
            species != Species.human
            and p.id != player.id
            and p.species == species
        ):
            raise ValueError(f"Species '{species.value}' is already taken")

    player.species = species
    await db.commit()
    await db.refresh(player)
    return player


async def start_game(db: AsyncSession, game: Game, user: User) -> Game:
    if game.host_user_id != user.id:
        raise ValueError("Only the host can start the game")

    players = await get_players_for_game(db, game.id)
    if len(players) < 2:
        raise ValueError("Need at least 2 players to start")

    players_without_species = [p for p in players if p.species is None]
    if players_without_species:
        raise ValueError("All players must select a species before starting")

    game.status = GameStatus.active
    game.current_round = 1
    await db.flush()

    # Generate the galaxy map
    await generate_map(db, game_id=game.id, players=players)

    # Initialize turn state (set active player, phase)
    await initialize_turn_state(db, game)

    # Allocate starting resources per species
    for player in players:
        await create_player_resources(player, db)

    # Initialize ship blueprints and place starting ships per species
    for player in players:
        await initialize_blueprints(player, db)
        await place_starting_ships(player, game.id, db)

    # Initialize the discovery tile deck (shuffled)
    await initialize_discovery_deck(db, game.id)

    await db.commit()
    await db.refresh(game)

    # Notify all players that the game has started (best-effort)
    from app.services.notification_service import notify_game_started
    await notify_game_started(db, game, players)

    return game


async def get_game_deletion_request(db: AsyncSession, game_id: int) -> GameDeletionRequest | None:
    result = await db.execute(
        select(GameDeletionRequest).where(GameDeletionRequest.game_id == game_id)
    )
    return result.scalar_one_or_none()


async def get_game_deletion_approvals(
    db: AsyncSession, request_id: int
) -> list[GameDeletionApproval]:
    result = await db.execute(
        select(GameDeletionApproval).where(GameDeletionApproval.request_id == request_id)
    )
    return list(result.scalars().all())


async def request_or_approve_game_deletion(
    db: AsyncSession, game: Game, user: User
) -> tuple[GameDeletionRequest, bool]:
    if game.host_user_id != user.id:
        raise ValueError("Only the host can request game deletion")

    players = await get_players_for_game(db, game.id)
    user_ids = {p.user_id for p in players}

    request = await get_game_deletion_request(db, game.id)
    if request is None:
        request = GameDeletionRequest(
            game_id=game.id,
            requested_by_user_id=user.id,
            status=GameDeletionRequestStatus.pending,
        )
        db.add(request)
        await db.flush()

        for uid in user_ids:
            db.add(
                GameDeletionApproval(
                    request_id=request.id,
                    user_id=uid,
                    approved=(uid == user.id),
                    approved_at=datetime.now(timezone.utc) if uid == user.id else None,
                )
            )
        await db.flush()
    else:
        if request.requested_by_user_id != user.id:
            raise ValueError("Deletion request already exists and was not created by this host")

    deleted = await _delete_game_if_all_approved(db, game, request)
    if not deleted:
        await db.commit()
        await db.refresh(request)
    return request, deleted


async def approve_game_deletion(
    db: AsyncSession, game: Game, user: User
) -> tuple[GameDeletionRequest, bool]:
    request = await get_game_deletion_request(db, game.id)
    if request is None:
        raise ValueError("Deletion request was not created")

    result = await db.execute(
        select(GameDeletionApproval).where(
            GameDeletionApproval.request_id == request.id,
            GameDeletionApproval.user_id == user.id,
        )
    )
    approval = result.scalar_one_or_none()
    if approval is None:
        raise ValueError("Only game players can approve deletion")

    approval.approved = True
    approval.approved_at = datetime.now(timezone.utc)

    deleted = await _delete_game_if_all_approved(db, game, request)
    if not deleted:
        await db.commit()
        await db.refresh(request)
    return request, deleted


async def _delete_game_if_all_approved(
    db: AsyncSession, game: Game, request: GameDeletionRequest
) -> bool:
    approvals = await get_game_deletion_approvals(db, request.id)
    if not approvals or any(not a.approved for a in approvals):
        return False

    player_ids = [p.id for p in await get_players_for_game(db, game.id)]

    await db.execute(delete(GameAction).where(GameAction.game_id == game.id))

    from app.models.combat_log import CombatLog
    from app.models.council import CouncilState
    from app.models.discovery_tile import DiscoveryTile
    from app.models.game_invite import GameInvite
    from app.models.hex_tile import HexTile
    from app.models.planet_population import PlanetPopulation
    from app.models.player_resources import PlayerResources
    from app.models.player_technology import PlayerTechnology
    from app.models.ship import Ship
    from app.models.ship_blueprint import ShipBlueprint
    from app.models.system import System

    if player_ids:
        await db.execute(delete(PlayerResources).where(PlayerResources.player_id.in_(player_ids)))
        await db.execute(delete(PlayerTechnology).where(PlayerTechnology.player_id.in_(player_ids)))
        await db.execute(delete(ShipBlueprint).where(ShipBlueprint.player_id.in_(player_ids)))
        await db.execute(delete(PlanetPopulation).where(PlanetPopulation.owner_player_id.in_(player_ids)))

    await db.execute(delete(CombatLog).where(CombatLog.game_id == game.id))
    await db.execute(delete(CouncilState).where(CouncilState.game_id == game.id))
    await db.execute(delete(DiscoveryTile).where(DiscoveryTile.game_id == game.id))
    await db.execute(delete(GameInvite).where(GameInvite.game_id == game.id))
    await db.execute(delete(Ship).where(Ship.game_id == game.id))

    tile_ids_result = await db.execute(select(HexTile.id).where(HexTile.game_id == game.id))
    tile_ids = [row[0] for row in tile_ids_result.all()]
    if tile_ids:
        await db.execute(delete(System).where(System.hex_tile_id.in_(tile_ids)))

    await db.execute(delete(HexTile).where(HexTile.game_id == game.id))
    await db.execute(delete(Player).where(Player.game_id == game.id))

    await db.execute(delete(GameDeletionApproval).where(GameDeletionApproval.request_id == request.id))
    await db.execute(delete(GameDeletionRequest).where(GameDeletionRequest.id == request.id))

    await db.delete(game)
    await db.commit()
    return True
