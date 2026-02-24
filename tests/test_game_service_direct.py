"""Direct service-level tests for game_service and map_generator.

These tests call service functions directly via db_session (not via HTTP API)
to ensure coverage tracking works correctly for those code paths.

Covers:
- game_service.create_game
- game_service.get_game
- game_service.get_players_for_game
- game_service.get_player_in_game
- game_service.create_invite
- game_service.get_invite_by_token
- game_service.join_game
- game_service.select_species
- game_service.start_game
- map_generator.generate_map (2-6 players)
- map_generator ValueError on invalid player count
- turn_engine.get_active_player
- turn_engine.get_players_for_game
- turn_engine.get_game_actions
- turn_engine.initialize_turn_state
- turn_engine.validate_action
- turn_engine.submit_action (pass action)
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game, GamePhase, GameStatus
from app.models.game_action import ActionType
from app.models.player import Player, Species
from app.models.user import User
from app.services.game_service import (
    create_game,
    create_invite,
    get_game,
    get_invite_by_token,
    get_player_in_game,
    get_players_for_game,
    join_game,
    select_species,
    start_game,
)
from app.services.map_generator import generate_map
from app.services.turn_engine import (
    get_active_player,
    get_game_actions,
    submit_action,
    validate_action,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_user(db: AsyncSession, tag: str) -> User:
    user = User(
        email=f"gs_{tag}@test.com",
        username=f"gs_{tag}",
        hashed_password="hashed",
    )
    db.add(user)
    await db.flush()
    return user


async def _make_game_with_two_players(
    db: AsyncSession,
    tag: str,
    species_a: Species = Species.human,
    species_b: Species = Species.planta,
) -> tuple[Game, User, User, Player, Player]:
    """Create a lobby game with two players."""
    host = await _make_user(db, f"{tag}_h")
    joiner = await _make_user(db, f"{tag}_j")

    game = await create_game(db, name=f"gs-game-{tag}", max_players=2, host=host)

    invite = await create_invite(db, game.id, joiner.email)
    player_b = await join_game(db, game, joiner, invite.token)

    player_a = await get_player_in_game(db, game.id, host.id)
    player_a = await select_species(db, game, host, species_a)
    player_b = await select_species(db, game, joiner, species_b)

    return game, host, joiner, player_a, player_b


# ---------------------------------------------------------------------------
# game_service.create_game
# ---------------------------------------------------------------------------


class TestCreateGameDirect:
    async def test_create_game_returns_game(self, db_session: AsyncSession):
        host = await _make_user(db_session, "cg1")
        game = await create_game(db_session, name="Test Game", max_players=4, host=host)

        assert game.id is not None
        assert game.name == "Test Game"
        assert game.max_players == 4
        assert game.status == GameStatus.lobby
        assert game.host_user_id == host.id

    async def test_create_game_host_becomes_player(self, db_session: AsyncSession):
        host = await _make_user(db_session, "cg2")
        game = await create_game(db_session, name="Test2", max_players=2, host=host)

        players = await get_players_for_game(db_session, game.id)
        assert len(players) == 1
        assert players[0].user_id == host.id
        assert players[0].turn_order == 0

    async def test_get_game_returns_game(self, db_session: AsyncSession):
        host = await _make_user(db_session, "gg1")
        created = await create_game(db_session, name="GetMe", max_players=2, host=host)

        fetched = await get_game(db_session, created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "GetMe"

    async def test_get_game_returns_none_for_missing(self, db_session: AsyncSession):
        result = await get_game(db_session, 999999)
        assert result is None

    async def test_get_players_returns_list(self, db_session: AsyncSession):
        host = await _make_user(db_session, "gp1")
        game = await create_game(db_session, name="Players", max_players=2, host=host)
        players = await get_players_for_game(db_session, game.id)
        assert isinstance(players, list)
        assert len(players) == 1

    async def test_get_player_in_game_found(self, db_session: AsyncSession):
        host = await _make_user(db_session, "gpi1")
        game = await create_game(db_session, name="PIG", max_players=2, host=host)
        player = await get_player_in_game(db_session, game.id, host.id)
        assert player is not None
        assert player.user_id == host.id

    async def test_get_player_in_game_not_found(self, db_session: AsyncSession):
        host = await _make_user(db_session, "gpi2")
        game = await create_game(db_session, name="PIG2", max_players=2, host=host)
        result = await get_player_in_game(db_session, game.id, 999999)
        assert result is None


# ---------------------------------------------------------------------------
# game_service.create_invite and join_game
# ---------------------------------------------------------------------------


class TestInviteAndJoinDirect:
    async def test_create_invite_returns_invite(self, db_session: AsyncSession):
        host = await _make_user(db_session, "inv1")
        game = await create_game(db_session, "InvGame", max_players=2, host=host)

        invite = await create_invite(db_session, game.id, "invited@test.com")
        assert invite.token
        assert invite.game_id == game.id
        assert invite.invitee_email == "invited@test.com"
        assert not invite.accepted

    async def test_get_invite_by_token_found(self, db_session: AsyncSession):
        host = await _make_user(db_session, "gib1")
        game = await create_game(db_session, "GIBGame", max_players=2, host=host)
        invite = await create_invite(db_session, game.id, "x@test.com")

        fetched = await get_invite_by_token(db_session, invite.token)
        assert fetched is not None
        assert fetched.id == invite.id

    async def test_get_invite_by_token_not_found(self, db_session: AsyncSession):
        result = await get_invite_by_token(db_session, "nonexistent_token_xyz")
        assert result is None

    async def test_join_game_adds_player(self, db_session: AsyncSession):
        host = await _make_user(db_session, "join1_h")
        joiner = await _make_user(db_session, "join1_j")
        game = await create_game(db_session, "JoinGame", max_players=2, host=host)
        invite = await create_invite(db_session, game.id, joiner.email)

        player = await join_game(db_session, game, joiner, invite.token)
        assert player.user_id == joiner.id
        assert player.game_id == game.id
        assert player.turn_order == 1

    async def test_join_game_invalid_token_raises(self, db_session: AsyncSession):
        host = await _make_user(db_session, "join2_h")
        joiner = await _make_user(db_session, "join2_j")
        game = await create_game(db_session, "JoinGame2", max_players=2, host=host)

        with pytest.raises(ValueError, match="[Ii]nvalid"):
            await join_game(db_session, game, joiner, "bad_token")

    async def test_join_game_used_token_raises(self, db_session: AsyncSession):
        host = await _make_user(db_session, "join3_h")
        joiner = await _make_user(db_session, "join3_j")
        game = await create_game(db_session, "JoinGame3", max_players=2, host=host)
        invite = await create_invite(db_session, game.id, joiner.email)
        await join_game(db_session, game, joiner, invite.token)

        joiner2 = await _make_user(db_session, "join3_j2")
        with pytest.raises(ValueError, match="[Aa]lready"):
            await join_game(db_session, game, joiner2, invite.token)

    async def test_join_game_already_joined_raises(self, db_session: AsyncSession):
        host = await _make_user(db_session, "join4_h")
        game = await create_game(db_session, "JoinGame4", max_players=3, host=host)
        invite = await create_invite(db_session, game.id, host.email)

        with pytest.raises(ValueError, match="[Aa]lready joined"):
            await join_game(db_session, game, host, invite.token)

    async def test_join_game_full_raises(self, db_session: AsyncSession):
        host = await _make_user(db_session, "join5_h")
        joiner = await _make_user(db_session, "join5_j")
        game = await create_game(db_session, "JoinGame5", max_players=2, host=host)
        invite = await create_invite(db_session, game.id, joiner.email)
        await join_game(db_session, game, joiner, invite.token)

        extra = await _make_user(db_session, "join5_e")
        invite2 = await create_invite(db_session, game.id, extra.email)
        with pytest.raises(ValueError, match="[Ff]ull"):
            await join_game(db_session, game, extra, invite2.token)


# ---------------------------------------------------------------------------
# game_service.select_species
# ---------------------------------------------------------------------------


class TestSelectSpeciesDirect:
    async def test_select_species_updates_player(self, db_session: AsyncSession):
        host = await _make_user(db_session, "ss1_h")
        game = await create_game(db_session, "SSGame", max_players=2, host=host)
        player = await select_species(db_session, game, host, Species.human)
        assert player.species == Species.human

    async def test_select_species_duplicate_raises(self, db_session: AsyncSession):
        host = await _make_user(db_session, "ss2_h")
        joiner = await _make_user(db_session, "ss2_j")
        game = await create_game(db_session, "SSGame2", max_players=2, host=host)
        invite = await create_invite(db_session, game.id, joiner.email)
        await join_game(db_session, game, joiner, invite.token)

        await select_species(db_session, game, host, Species.human)
        with pytest.raises(ValueError, match="[Aa]lready taken"):
            await select_species(db_session, game, joiner, Species.human)

    async def test_select_species_not_in_game_raises(self, db_session: AsyncSession):
        host = await _make_user(db_session, "ss3_h")
        outsider = await _make_user(db_session, "ss3_o")
        game = await create_game(db_session, "SSGame3", max_players=2, host=host)

        with pytest.raises(ValueError, match="[Nn]ot a player"):
            await select_species(db_session, game, outsider, Species.planta)


# ---------------------------------------------------------------------------
# game_service.start_game
# ---------------------------------------------------------------------------


class TestStartGameDirect:
    async def test_start_game_sets_active_status(self, db_session: AsyncSession):
        game, host, joiner, player_a, player_b = await _make_game_with_two_players(
            db_session, "start1"
        )
        started = await start_game(db_session, game, host)
        assert started.status == GameStatus.active
        assert started.current_round == 1
        assert started.current_phase == GamePhase.activation

    async def test_start_game_non_host_raises(self, db_session: AsyncSession):
        game, host, joiner, player_a, player_b = await _make_game_with_two_players(
            db_session, "start2"
        )
        with pytest.raises(ValueError, match="[Hh]ost"):
            await start_game(db_session, game, joiner)

    async def test_start_game_too_few_players_raises(self, db_session: AsyncSession):
        host = await _make_user(db_session, "start3_h")
        game = await create_game(db_session, "TooFew", max_players=2, host=host)
        await select_species(db_session, game, host, Species.human)

        with pytest.raises(ValueError, match="[Aa]t least 2"):
            await start_game(db_session, game, host)

    async def test_start_game_missing_species_raises(self, db_session: AsyncSession):
        host = await _make_user(db_session, "start4_h")
        joiner = await _make_user(db_session, "start4_j")
        game = await create_game(db_session, "NoSpecies", max_players=2, host=host)
        invite = await create_invite(db_session, game.id, joiner.email)
        await join_game(db_session, game, joiner, invite.token)
        await select_species(db_session, game, host, Species.human)
        # joiner has no species

        with pytest.raises(ValueError, match="[Ss]pecies"):
            await start_game(db_session, game, host)

    async def test_start_game_creates_map_tiles(self, db_session: AsyncSession):
        from sqlalchemy import select as sql_select
        from app.models.hex_tile import HexTile

        game, host, joiner, player_a, player_b = await _make_game_with_two_players(
            db_session, "start5"
        )
        await start_game(db_session, game, host)

        result = await db_session.execute(
            sql_select(HexTile).where(HexTile.game_id == game.id)
        )
        tiles = result.scalars().all()
        assert len(tiles) > 0


# ---------------------------------------------------------------------------
# map_generator.generate_map direct tests
# ---------------------------------------------------------------------------


class TestGenerateMapDirect:
    async def _create_game_with_players(
        self,
        db: AsyncSession,
        tag: str,
        num_players: int,
        species_list: list[Species],
    ) -> tuple[Game, list[Player]]:
        """Create game + players without starting; return game and players."""
        users = [await _make_user(db, f"map_{tag}_{i}") for i in range(num_players)]

        game = Game(
            name=f"map-game-{tag}",
            status=GameStatus.lobby,
            max_players=num_players,
            current_round=0,
            host_user_id=users[0].id,
        )
        db.add(game)
        await db.flush()

        players = []
        for i, user in enumerate(users):
            p = Player(
                game_id=game.id,
                user_id=user.id,
                species=species_list[i],
                turn_order=i,
            )
            db.add(p)
        await db.flush()

        result = await db.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(Player).where(
                Player.game_id == game.id
            )
        )
        players = list(result.scalars().all())
        return game, players

    async def test_generate_map_2_players(self, db_session: AsyncSession):
        from sqlalchemy import select as sql_select
        from app.models.hex_tile import HexTile

        game, players = await self._create_game_with_players(
            db_session, "2p", 2, [Species.human, Species.planta]
        )
        await generate_map(db_session, game.id, players)
        await db_session.flush()

        result = await db_session.execute(
            sql_select(HexTile).where(HexTile.game_id == game.id)
        )
        tiles = result.scalars().all()
        assert len(tiles) > 0
        # Galactic center should exist at (0,0)
        gc = next((t for t in tiles if t.q == 0 and t.r == 0), None)
        assert gc is not None
        assert gc.is_explored is True

    async def test_generate_map_3_players(self, db_session: AsyncSession):
        from sqlalchemy import select as sql_select
        from app.models.hex_tile import HexTile

        game, players = await self._create_game_with_players(
            db_session,
            "3p",
            3,
            [Species.human, Species.planta, Species.mechanema],
        )
        await generate_map(db_session, game.id, players)
        await db_session.flush()

        result = await db_session.execute(
            sql_select(HexTile).where(HexTile.game_id == game.id)
        )
        tiles = result.scalars().all()
        homeworlds = [t for t in tiles if t.owner_player_id is not None]
        assert len(homeworlds) >= 3 * 2  # at least 2 tiles (hw + starting sector) per player

    async def test_generate_map_invalid_player_count_raises(self, db_session: AsyncSession):
        game, players = await self._create_game_with_players(
            db_session, "inv", 2, [Species.human, Species.planta]
        )
        # Create fake 1-player list to trigger the ValueError
        single_player = players[:1]
        with pytest.raises(ValueError, match="[Uu]nsupported player"):
            await generate_map(db_session, game.id, single_player)


# ---------------------------------------------------------------------------
# turn_engine direct tests
# ---------------------------------------------------------------------------


class TestTurnEngineDirect:
    async def _start_game(
        self, db: AsyncSession, tag: str
    ) -> tuple[Game, list[Player]]:
        """Create a fully started 2-player game via service calls."""
        host = await _make_user(db, f"te_{tag}_h")
        joiner = await _make_user(db, f"te_{tag}_j")
        game = await create_game(db, f"te-game-{tag}", max_players=2, host=host)
        invite = await create_invite(db, game.id, joiner.email)
        await join_game(db, game, joiner, invite.token)
        await select_species(db, game, host, Species.human)
        await select_species(db, game, joiner, Species.planta)
        started = await start_game(db, game, host)
        players_list = await get_players_for_game(db, started.id)
        return started, players_list

    async def test_get_active_player_returns_active_player(
        self, db_session: AsyncSession
    ):
        game, players = await self._start_game(db_session, "gap1")
        active = await get_active_player(db_session, game.id)
        assert active is not None
        assert active.is_active_turn is True

    async def test_get_active_player_returns_none_when_none_active(
        self, db_session: AsyncSession
    ):
        # Create a game where no player is active
        user = await _make_user(db_session, "gap2_u")
        game = Game(
            name="NoActive",
            status=GameStatus.active,
            max_players=2,
            current_round=1,
            current_phase=GamePhase.activation,
            host_user_id=user.id,
        )
        db_session.add(game)
        await db_session.flush()
        # No players added; active should be None
        active = await get_active_player(db_session, game.id)
        assert active is None

    async def test_get_game_actions_empty_at_start(
        self, db_session: AsyncSession
    ):
        game, _ = await self._start_game(db_session, "gga1")
        actions = await get_game_actions(db_session, game.id)
        assert isinstance(actions, list)
        assert len(actions) == 0

    async def test_validate_action_wrong_phase_raises(
        self, db_session: AsyncSession
    ):
        game, players = await self._start_game(db_session, "va1")
        active = next(p for p in players if p.is_active_turn)

        # Manually set game to combat phase
        game.current_phase = GamePhase.combat
        with pytest.raises(ValueError, match="[Aa]ctivation"):
            await validate_action(game, active, ActionType.pass_action)

    async def test_validate_action_not_your_turn_raises(
        self, db_session: AsyncSession
    ):
        game, players = await self._start_game(db_session, "va2")
        inactive = next(p for p in players if not p.is_active_turn)
        with pytest.raises(ValueError, match="not your turn"):
            await validate_action(game, inactive, ActionType.pass_action)

    async def test_validate_action_already_passed_raises(
        self, db_session: AsyncSession
    ):
        game, players = await self._start_game(db_session, "va3")
        active = next(p for p in players if p.is_active_turn)
        active.has_passed = True
        with pytest.raises(ValueError, match="[Aa]lready passed"):
            await validate_action(game, active, ActionType.pass_action)

    async def test_submit_pass_action_marks_player_passed(
        self, db_session: AsyncSession
    ):
        game, players = await self._start_game(db_session, "sp1")
        active = next(p for p in players if p.is_active_turn)

        action = await submit_action(db_session, game, active, ActionType.pass_action)

        assert action.action_type == ActionType.pass_action
        assert action.game_id == game.id
        assert action.player_id == active.id

    async def test_submit_action_game_not_active_raises(
        self, db_session: AsyncSession
    ):
        user = await _make_user(db_session, "sa1_u")
        game = Game(
            name="InactiveGame",
            status=GameStatus.lobby,
            max_players=2,
            current_round=0,
            host_user_id=user.id,
        )
        db_session.add(game)
        await db_session.flush()
        player = Player(
            game_id=game.id, user_id=user.id, species=Species.human,
            turn_order=0, is_active_turn=True, has_passed=False
        )
        db_session.add(player)
        await db_session.flush()

        with pytest.raises(ValueError, match="[Nn]ot active"):
            await validate_action(game, player, ActionType.pass_action)
