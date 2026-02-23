import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game, GameStatus
from app.models.game_invite import GameInvite
from app.models.player import Player, Species
from app.models.user import User
from app.services.map_generator import generate_map


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


async def join_game(db: AsyncSession, game: Game, user: User, token: str) -> Player:
    invite = await get_invite_by_token(db, token)
    if invite is None or invite.game_id != game.id:
        raise ValueError("Invalid invite token")
    if invite.accepted:
        raise ValueError("Invite already used")

    existing = await get_player_in_game(db, game.id, user.id)
    if existing is not None:
        raise ValueError("Already joined this game")

    players = await get_players_for_game(db, game.id)
    if len(players) >= game.max_players:
        raise ValueError("Game is full")

    invite.accepted = True
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

    # Check no other player has already chosen this species
    players = await get_players_for_game(db, game.id)
    for p in players:
        if p.id != player.id and p.species == species:
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

    await db.commit()
    await db.refresh(game)
    return game
