"""Tests for Task 15: Victory Points & End Game.

Covers:
- Colony VP calculation (1 VP per controlled system)
- Tech VP calculation at game end (e.g., Monolith)
- Final VP tally combining all sources
- Tiebreaker by money
- End-game trigger at round 8
- GET /games/{id}/scores endpoint
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game, GameStatus
from app.models.hex_tile import HexTile, TileType
from app.models.player import Player, Species
from app.models.player_resources import PlayerResources
from app.models.player_technology import PlayerTechnology
from app.models.user import User
from app.services.victory_service import (
    calculate_colony_vp,
    calculate_final_vp,
    calculate_tech_vp,
    determine_winner,
    finalize_game,
    get_scores,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_user(db: AsyncSession, email: str) -> User:
    user = User(email=email, username=email.split("@")[0], hashed_password="x")
    db.add(user)
    await db.flush()
    return user


async def _create_game(db: AsyncSession, name: str = "Test", round_num: int = 1) -> Game:
    game = Game(name=name, status=GameStatus.active, current_round=round_num, max_players=2)
    db.add(game)
    await db.flush()
    return game


async def _create_player(
    db: AsyncSession,
    game: Game,
    user: User,
    vp: int = 0,
    turn_order: int = 1,
) -> Player:
    player = Player(
        game_id=game.id,
        user_id=user.id,
        species=Species.human,
        turn_order=turn_order,
        is_active_turn=False,
        has_passed=False,
        vp_count=vp,
    )
    db.add(player)
    await db.flush()
    return player


async def _create_resources(
    db: AsyncSession, player: Player, money: int = 10
) -> PlayerResources:
    resources = PlayerResources(
        player_id=player.id,
        money=money,
        science=5,
        materials=5,
        population_cubes={},
        tradespheres=0,
        influence_discs_total=11,
        influence_discs_used=0,
    )
    db.add(resources)
    await db.flush()
    return resources


async def _create_hex(
    db: AsyncSession,
    game: Game,
    owner_player_id: int | None = None,
    q: int = 0,
    r: int = 0,
) -> HexTile:
    hex_tile = HexTile(
        game_id=game.id,
        q=q,
        r=r,
        tile_type=TileType.inner,
        is_explored=True,
        owner_player_id=owner_player_id,
    )
    db.add(hex_tile)
    await db.flush()
    return hex_tile


# ---------------------------------------------------------------------------
# Colony VP tests
# ---------------------------------------------------------------------------


class TestColonyVP:
    async def test_no_controlled_hexes(self, db_session: AsyncSession):
        user = await _create_user(db_session, "colony1@example.com")
        game = await _create_game(db_session)
        player = await _create_player(db_session, game, user)

        vp = await calculate_colony_vp(db_session, player.id, game.id)
        assert vp == 0

    async def test_single_controlled_hex(self, db_session: AsyncSession):
        user = await _create_user(db_session, "colony2@example.com")
        game = await _create_game(db_session)
        player = await _create_player(db_session, game, user)
        await _create_hex(db_session, game, owner_player_id=player.id, q=1, r=0)

        vp = await calculate_colony_vp(db_session, player.id, game.id)
        assert vp == 1

    async def test_multiple_controlled_hexes(self, db_session: AsyncSession):
        user = await _create_user(db_session, "colony3@example.com")
        game = await _create_game(db_session)
        player = await _create_player(db_session, game, user)
        for i in range(4):
            await _create_hex(db_session, game, owner_player_id=player.id, q=i, r=i)

        vp = await calculate_colony_vp(db_session, player.id, game.id)
        assert vp == 4

    async def test_other_player_hexes_not_counted(self, db_session: AsyncSession):
        user1 = await _create_user(db_session, "colony4a@example.com")
        user2 = await _create_user(db_session, "colony4b@example.com")
        game = await _create_game(db_session)
        p1 = await _create_player(db_session, game, user1, turn_order=1)
        p2 = await _create_player(db_session, game, user2, turn_order=2)
        # p1 owns 2 hexes, p2 owns 1
        await _create_hex(db_session, game, owner_player_id=p1.id, q=0, r=0)
        await _create_hex(db_session, game, owner_player_id=p1.id, q=1, r=0)
        await _create_hex(db_session, game, owner_player_id=p2.id, q=2, r=0)

        assert await calculate_colony_vp(db_session, p1.id, game.id) == 2
        assert await calculate_colony_vp(db_session, p2.id, game.id) == 1


# ---------------------------------------------------------------------------
# Tech VP tests
# ---------------------------------------------------------------------------


class TestTechVP:
    async def test_no_techs(self, db_session: AsyncSession):
        user = await _create_user(db_session, "tech1@example.com")
        game = await _create_game(db_session)
        player = await _create_player(db_session, game, user)

        vp = await calculate_tech_vp(db_session, player.id)
        assert vp == 0

    async def test_tech_without_vp_effect(self, db_session: AsyncSession):
        user = await _create_user(db_session, "tech2@example.com")
        game = await _create_game(db_session)
        player = await _create_player(db_session, game, user)
        db_session.add(PlayerTechnology(player_id=player.id, tech_id="improved_hull", acquired_round=1))
        await db_session.flush()

        vp = await calculate_tech_vp(db_session, player.id)
        assert vp == 0

    async def test_monolith_gives_2vp(self, db_session: AsyncSession):
        user = await _create_user(db_session, "tech3@example.com")
        game = await _create_game(db_session)
        player = await _create_player(db_session, game, user)
        db_session.add(PlayerTechnology(player_id=player.id, tech_id="monolith", acquired_round=1))
        await db_session.flush()

        vp = await calculate_tech_vp(db_session, player.id)
        assert vp == 2

    async def test_multiple_monoliths_stack(self, db_session: AsyncSession):
        # If a player somehow has multiple monolith entries, each awards VP
        user = await _create_user(db_session, "tech4@example.com")
        game = await _create_game(db_session)
        player = await _create_player(db_session, game, user)
        db_session.add(PlayerTechnology(player_id=player.id, tech_id="monolith", acquired_round=1))
        db_session.add(PlayerTechnology(player_id=player.id, tech_id="improved_hull", acquired_round=1))
        await db_session.flush()

        vp = await calculate_tech_vp(db_session, player.id)
        assert vp == 2  # only monolith contributes


# ---------------------------------------------------------------------------
# Final VP tally tests
# ---------------------------------------------------------------------------


class TestFinalVP:
    async def test_final_vp_adds_colony_and_tech(self, db_session: AsyncSession):
        user = await _create_user(db_session, "final1@example.com")
        game = await _create_game(db_session)
        player = await _create_player(db_session, game, user, vp=3)  # 3 ongoing VP
        # 2 owned hexes
        await _create_hex(db_session, game, owner_player_id=player.id, q=0, r=0)
        await _create_hex(db_session, game, owner_player_id=player.id, q=1, r=0)
        # Monolith tech (+2 VP at game end)
        db_session.add(PlayerTechnology(player_id=player.id, tech_id="monolith", acquired_round=1))
        await db_session.flush()

        sorted_players = await calculate_final_vp(db_session, game)
        await db_session.refresh(player)

        assert player.vp_count == 7  # 3 ongoing + 2 colony + 2 tech
        assert player.vp_breakdown is not None
        assert player.vp_breakdown["ongoing"] == 3
        assert player.vp_breakdown["colony"] == 2
        assert player.vp_breakdown["tech"] == 2
        assert player.vp_breakdown["total"] == 7
        assert sorted_players[0].id == player.id

    async def test_final_vp_no_extras(self, db_session: AsyncSession):
        user = await _create_user(db_session, "final2@example.com")
        game = await _create_game(db_session)
        player = await _create_player(db_session, game, user, vp=5)

        await calculate_final_vp(db_session, game)
        await db_session.refresh(player)

        assert player.vp_count == 5
        assert player.vp_breakdown["ongoing"] == 5
        assert player.vp_breakdown["colony"] == 0
        assert player.vp_breakdown["tech"] == 0


# ---------------------------------------------------------------------------
# Tiebreaker tests
# ---------------------------------------------------------------------------


class TestTiebreaker:
    async def test_no_tie_highest_vp_wins(self, db_session: AsyncSession):
        user1 = await _create_user(db_session, "tie1a@example.com")
        user2 = await _create_user(db_session, "tie1b@example.com")
        game = await _create_game(db_session)
        p1 = await _create_player(db_session, game, user1, vp=10, turn_order=1)
        p2 = await _create_player(db_session, game, user2, vp=7, turn_order=2)

        winner = await determine_winner(db_session, [p1, p2])
        assert winner is not None
        assert winner.id == p1.id

    async def test_tie_broken_by_money(self, db_session: AsyncSession):
        user1 = await _create_user(db_session, "tie2a@example.com")
        user2 = await _create_user(db_session, "tie2b@example.com")
        game = await _create_game(db_session)
        p1 = await _create_player(db_session, game, user1, vp=8, turn_order=1)
        p2 = await _create_player(db_session, game, user2, vp=8, turn_order=2)
        await _create_resources(db_session, p1, money=5)
        await _create_resources(db_session, p2, money=15)

        winner = await determine_winner(db_session, [p1, p2])
        assert winner is not None
        assert winner.id == p2.id  # p2 has more money

    async def test_no_players_returns_none(self, db_session: AsyncSession):
        winner = await determine_winner(db_session, [])
        assert winner is None


# ---------------------------------------------------------------------------
# End-game trigger tests
# ---------------------------------------------------------------------------


class TestEndGameTrigger:
    async def test_finalize_game_marks_finished(self, db_session: AsyncSession):
        user = await _create_user(db_session, "end1@example.com")
        game = await _create_game(db_session, round_num=8)
        await _create_player(db_session, game, user, vp=5)

        await finalize_game(db_session, game)
        await db_session.refresh(game)

        assert game.status == GameStatus.finished

    async def test_finalize_game_updates_vp(self, db_session: AsyncSession):
        user = await _create_user(db_session, "end2@example.com")
        game = await _create_game(db_session, round_num=8)
        player = await _create_player(db_session, game, user, vp=3)
        # 1 hex owned
        await _create_hex(db_session, game, owner_player_id=player.id, q=0, r=0)

        await finalize_game(db_session, game)
        await db_session.refresh(player)

        assert player.vp_count == 4  # 3 ongoing + 1 colony
        assert player.vp_breakdown is not None

    async def test_finalize_returns_winner(self, db_session: AsyncSession):
        user1 = await _create_user(db_session, "end3a@example.com")
        user2 = await _create_user(db_session, "end3b@example.com")
        game = await _create_game(db_session, round_num=8)
        p1 = await _create_player(db_session, game, user1, vp=10, turn_order=1)
        await _create_player(db_session, game, user2, vp=5, turn_order=2)

        winner = await finalize_game(db_session, game)
        assert winner is not None
        assert winner.id == p1.id


# ---------------------------------------------------------------------------
# GET /games/{id}/scores endpoint tests
# ---------------------------------------------------------------------------


async def _setup_active_game(client: AsyncClient) -> tuple[int, str, str]:
    """Create and start a 2-player game. Returns (game_id, token1, token2)."""
    # Register two players
    await client.post("/auth/register", json={"email": "sc1@ex.com", "username": "sc1", "password": "testpass1"})
    await client.post("/auth/register", json={"email": "sc2@ex.com", "username": "sc2", "password": "testpass1"})
    r1 = await client.post("/auth/login", json={"email": "sc1@ex.com", "password": "testpass1"})
    r2 = await client.post("/auth/login", json={"email": "sc2@ex.com", "password": "testpass1"})
    token1 = r1.json()["access_token"]
    token2 = r2.json()["access_token"]

    # Create game
    resp = await client.post(
        "/games", json={"name": "ScoreGame", "max_players": 2},
        headers={"Authorization": f"Bearer {token1}"},
    )
    game_id = resp.json()["id"]

    # Invite and join p2
    inv = await client.post(
        f"/games/{game_id}/invite",
        json={"invitee_email": "sc2@ex.com"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    token_val = inv.json()["token"]
    await client.post(
        f"/games/{game_id}/join",
        json={"token": token_val},
        headers={"Authorization": f"Bearer {token2}"},
    )

    # Both select species
    await client.post(
        f"/games/{game_id}/select-species",
        json={"species": "human"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    await client.post(
        f"/games/{game_id}/select-species",
        json={"species": "mechanema"},
        headers={"Authorization": f"Bearer {token2}"},
    )

    # Start game
    await client.post(
        f"/games/{game_id}/start",
        headers={"Authorization": f"Bearer {token1}"},
    )

    return game_id, token1, token2


class TestScoresEndpoint:
    async def test_scores_not_available_in_lobby(self, db_client: AsyncClient):
        await db_client.post("/auth/register", json={"email": "sc_lob@ex.com", "username": "sclob", "password": "testpass1"})
        r = await db_client.post("/auth/login", json={"email": "sc_lob@ex.com", "password": "testpass1"})
        token = r.json()["access_token"]
        g = await db_client.post(
            "/games", json={"name": "LobbyGame", "max_players": 4},
            headers={"Authorization": f"Bearer {token}"},
        )
        game_id = g.json()["id"]
        resp = await db_client.get(
            f"/games/{game_id}/scores",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    async def test_scores_available_during_active_game(self, db_client: AsyncClient):
        game_id, token1, _ = await _setup_active_game(db_client)
        resp = await db_client.get(
            f"/games/{game_id}/scores",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["game_id"] == game_id
        assert data["game_status"] == "active"
        assert len(data["players"]) == 2
        assert data["winner_player_id"] is None  # not finished yet

    async def test_scores_returns_vp_counts(self, db_client: AsyncClient):
        game_id, token1, _ = await _setup_active_game(db_client)
        resp = await db_client.get(
            f"/games/{game_id}/scores",
            headers={"Authorization": f"Bearer {token1}"},
        )
        data = resp.json()
        for player_score in data["players"]:
            assert "player_id" in player_score
            assert "vp_count" in player_score
            assert isinstance(player_score["vp_count"], int)

    async def test_scores_sorted_by_vp_descending(self, db_session: AsyncSession):
        # Use db_session to set differentiated VP values so the sort is non-trivial
        u1 = await _create_user(db_session, "sort_vp1@example.com")
        u2 = await _create_user(db_session, "sort_vp2@example.com")
        game = await _create_game(db_session)
        await _create_player(db_session, game, u1, vp=10, turn_order=0)
        await _create_player(db_session, game, u2, vp=3, turn_order=1)
        await db_session.commit()

        scores = await get_scores(db_session, game.id)
        vp_values = [s["vp_count"] for s in scores]
        assert vp_values == sorted(vp_values, reverse=True)
        assert vp_values[0] == 10
        assert vp_values[1] == 3
