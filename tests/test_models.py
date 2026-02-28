"""Unit tests for database models: User, Game, Player, GameInvite."""

import pytest
from sqlalchemy import select

from app.models.game import Game, GamePhase, GameStatus
from app.models.game_invite import GameInvite
from app.models.player import Player, Species
from app.models.user import User


class TestUserModel:
    async def test_create_user(self, db_session):
        user = User(
            email="alice@example.com",
            username="alice",
            hashed_password="hashed_pw",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.id is not None
        assert user.email == "alice@example.com"
        assert user.username == "alice"
        assert user.hashed_password == "hashed_pw"
        assert user.created_at is not None

    async def test_read_user(self, db_session):
        user = User(email="bob@example.com", username="bob", hashed_password="pw2")
        db_session.add(user)
        await db_session.commit()

        result = await db_session.execute(select(User).where(User.email == "bob@example.com"))
        fetched = result.scalar_one()
        assert fetched.username == "bob"

    async def test_user_email_unique(self, db_session):
        user1 = User(email="dup@example.com", username="dup1", hashed_password="pw")
        user2 = User(email="dup@example.com", username="dup2", hashed_password="pw")
        db_session.add(user1)
        await db_session.commit()
        db_session.add(user2)
        with pytest.raises(Exception):
            await db_session.commit()

    async def test_user_username_unique(self, db_session):
        user1 = User(email="u1@example.com", username="sameuser", hashed_password="pw")
        user2 = User(email="u2@example.com", username="sameuser", hashed_password="pw")
        db_session.add(user1)
        await db_session.commit()
        db_session.add(user2)
        with pytest.raises(Exception):
            await db_session.commit()


class TestGameModel:
    async def test_create_game_defaults(self, db_session):
        game = Game(name="My Game")
        db_session.add(game)
        await db_session.commit()
        await db_session.refresh(game)

        assert game.id is not None
        assert game.name == "My Game"
        assert game.status == GameStatus.lobby
        assert game.current_round == 0
        assert game.current_phase is None
        assert game.max_players == 4
        assert game.created_at is not None

    async def test_create_game_custom(self, db_session):
        game = Game(
            name="Big Game",
            status=GameStatus.active,
            current_round=3,
            current_phase=GamePhase.combat,
            max_players=6,
        )
        db_session.add(game)
        await db_session.commit()
        await db_session.refresh(game)

        assert game.status == GameStatus.active
        assert game.current_round == 3
        assert game.current_phase == GamePhase.combat
        assert game.max_players == 6

    async def test_game_status_values(self, db_session):
        for status in GameStatus:
            game = Game(name=f"game_{status.value}", status=status)
            db_session.add(game)
        await db_session.commit()

        result = await db_session.execute(select(Game))
        games = result.scalars().all()
        statuses = {g.status for g in games}
        assert GameStatus.lobby in statuses
        assert GameStatus.active in statuses
        assert GameStatus.finished in statuses

    async def test_game_phase_values(self, db_session):
        for phase in GamePhase:
            game = Game(
                name=f"game_phase_{phase.value}",
                current_phase=phase,
            )
            db_session.add(game)
        await db_session.commit()

        result = await db_session.execute(select(Game).where(Game.current_phase.isnot(None)))
        games = result.scalars().all()
        phases = {g.current_phase for g in games}
        assert GamePhase.strategy in phases
        assert GamePhase.activation in phases
        assert GamePhase.combat in phases
        assert GamePhase.upkeep in phases


class TestPlayerModel:
    async def _create_game_and_user(self, db_session):
        game = Game(name="Test Game")
        user = User(email="player@example.com", username="player1", hashed_password="pw")
        db_session.add(game)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(game)
        await db_session.refresh(user)
        return game, user

    async def test_create_player_defaults(self, db_session):
        game, user = await self._create_game_and_user(db_session)
        player = Player(game_id=game.id, user_id=user.id)
        db_session.add(player)
        await db_session.commit()
        await db_session.refresh(player)

        assert player.id is not None
        assert player.game_id == game.id
        assert player.user_id == user.id
        assert player.species is None
        assert player.turn_order is None
        assert player.is_active_turn is False
        assert player.vp_count == 0

    async def test_create_player_with_species(self, db_session):
        game, user = await self._create_game_and_user(db_session)
        player = Player(
            game_id=game.id,
            user_id=user.id,
            species=Species.human,
            turn_order=1,
            is_active_turn=True,
            vp_count=5,
        )
        db_session.add(player)
        await db_session.commit()
        await db_session.refresh(player)

        assert player.species == Species.human
        assert player.turn_order == 1
        assert player.is_active_turn is True
        assert player.vp_count == 5

    async def test_all_species_values(self, db_session):
        game = Game(name="Species Test Game")
        db_session.add(game)
        await db_session.commit()
        await db_session.refresh(game)

        for i, species in enumerate(Species):
            user = User(
                email=f"species_{i}@example.com",
                username=f"species_user_{i}",
                hashed_password="pw",
            )
            db_session.add(user)
            await db_session.commit()
            await db_session.refresh(user)

            player = Player(game_id=game.id, user_id=user.id, species=species)
            db_session.add(player)
        await db_session.commit()

        result = await db_session.execute(
            select(Player).where(Player.game_id == game.id)
        )
        players = result.scalars().all()
        assert len(players) == len(Species)

    async def test_player_foreign_keys(self, db_session):
        game, user = await self._create_game_and_user(db_session)
        player = Player(game_id=game.id, user_id=user.id)
        db_session.add(player)
        await db_session.commit()

        result = await db_session.execute(
            select(Player).where(Player.game_id == game.id)
        )
        fetched = result.scalar_one()
        assert fetched.user_id == user.id


class TestGameInviteModel:
    async def _create_game(self, db_session):
        game = Game(name="Invite Game")
        db_session.add(game)
        await db_session.commit()
        await db_session.refresh(game)
        return game

    async def test_create_invite_defaults(self, db_session):
        game = await self._create_game(db_session)
        invite = GameInvite(
            game_id=game.id,
            invitee_email="newplayer@example.com",
            token="unique-token-123",
        )
        db_session.add(invite)
        await db_session.commit()
        await db_session.refresh(invite)

        assert invite.id is not None
        assert invite.game_id == game.id
        assert invite.invitee_email == "newplayer@example.com"
        assert invite.token == "unique-token-123"
        assert invite.accepted is False

    async def test_invite_accepted(self, db_session):
        game = await self._create_game(db_session)
        invite = GameInvite(
            game_id=game.id,
            invitee_email="accepted@example.com",
            token="accepted-token",
            accepted=True,
        )
        db_session.add(invite)
        await db_session.commit()
        await db_session.refresh(invite)

        assert invite.accepted is True

    async def test_invite_token_unique(self, db_session):
        game = await self._create_game(db_session)
        invite1 = GameInvite(
            game_id=game.id, invitee_email="a@example.com", token="same-token"
        )
        invite2 = GameInvite(
            game_id=game.id, invitee_email="b@example.com", token="same-token"
        )
        db_session.add(invite1)
        await db_session.commit()
        db_session.add(invite2)
        with pytest.raises(Exception):
            await db_session.commit()

    async def test_invite_foreign_key(self, db_session):
        game = await self._create_game(db_session)
        invite = GameInvite(
            game_id=game.id, invitee_email="fk@example.com", token="fk-token"
        )
        db_session.add(invite)
        await db_session.commit()

        result = await db_session.execute(
            select(GameInvite).where(GameInvite.game_id == game.id)
        )
        fetched = result.scalar_one()
        assert fetched.invitee_email == "fk@example.com"
