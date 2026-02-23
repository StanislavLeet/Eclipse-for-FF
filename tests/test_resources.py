"""Tests for Task 7: Resource Management.

Covers:
- Starting resource allocation per species
- Influence disc tracking (use on action, reset on upkeep)
- BUILD material cost deduction and insufficient-material rejection
- RESEARCH science cost deduction and insufficient-science rejection
- Upkeep calculation (income + influence cost + bankruptcy)
- GET /games/{id}/players/{id}/resources endpoint
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.player_resources import PlayerResources
from app.services.resource_service import (
    apply_upkeep_for_game,
    get_player_resources,
    perform_upkeep_for_player,
    use_influence_disc,
    validate_and_deduct_build_cost,
    validate_and_deduct_research_cost,
)


# ---------------------------------------------------------------------------
# Shared helpers (mirror test_turn_engine.py pattern)
# ---------------------------------------------------------------------------

async def register_and_login(
    client: AsyncClient, email: str, username: str, password: str = "pass123"
) -> str:
    await client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


SPECIES_CYCLE = [
    "human",
    "planta",
    "mechanema",
    "orion_hegemony",
    "eridani_empire",
    "hydran_progress",
]


async def setup_started_game(
    client: AsyncClient, num_players: int = 2, species_list: list[str] | None = None
) -> tuple[list[str], dict]:
    """Create, populate, and start a game. Returns (tokens, game_dict)."""
    if species_list is None:
        species_list = SPECIES_CYCLE[:num_players]

    tokens = []
    emails = [f"res_p{i}@example.com" for i in range(num_players)]
    usernames = [f"res_player{i}" for i in range(num_players)]

    for i in range(num_players):
        token = await register_and_login(client, emails[i], usernames[i])
        tokens.append(token)

    create_resp = await client.post(
        "/games",
        json={"name": "Resource Test Game", "max_players": num_players},
        headers=auth_headers(tokens[0]),
    )
    assert create_resp.status_code == 201
    game_id = create_resp.json()["id"]

    for i in range(1, num_players):
        invite_resp = await client.post(
            f"/games/{game_id}/invite",
            json={"invitee_email": emails[i]},
            headers=auth_headers(tokens[0]),
        )
        invite_token = invite_resp.json()["token"]
        await client.post(
            f"/games/{game_id}/join",
            json={"token": invite_token},
            headers=auth_headers(tokens[i]),
        )

    for i in range(num_players):
        await client.post(
            f"/games/{game_id}/select-species",
            json={"species": species_list[i]},
            headers=auth_headers(tokens[i]),
        )

    start_resp = await client.post(
        f"/games/{game_id}/start", headers=auth_headers(tokens[0])
    )
    assert start_resp.status_code == 200
    return tokens, start_resp.json()


async def get_resources(client: AsyncClient, game_id: int, player_id: int, token: str) -> dict:
    resp = await client.get(
        f"/games/{game_id}/players/{player_id}/resources",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    return resp.json()


# ---------------------------------------------------------------------------
# Starting resource allocation
# ---------------------------------------------------------------------------

class TestStartingResources:
    async def test_resources_created_on_game_start(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        players = game["players"]

        for i, player in enumerate(players):
            data = await get_resources(db_client, game_id, player["id"], tokens[i])
            assert "money" in data
            assert "science" in data
            assert "materials" in data
            assert "influence_discs_total" in data
            assert data["influence_discs_total"] == 11
            assert data["influence_discs_used"] == 0
            assert data["influence_discs_remaining"] == 11

    async def test_human_starting_resources(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["human", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        data = await get_resources(db_client, game_id, host_player["id"], tokens[0])
        assert data["money"] == 3
        assert data["science"] == 3
        assert data["materials"] == 3

    async def test_mechanema_starting_resources(self, db_client: AsyncClient):
        """Mechanema starts with 6 materials."""
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["mechanema", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        data = await get_resources(db_client, game_id, host_player["id"], tokens[0])
        assert data["materials"] == 6
        assert data["money"] == 2
        assert data["science"] == 2

    async def test_hydran_starting_resources(self, db_client: AsyncClient):
        """Hydran Progress starts with 6 science."""
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["hydran_progress", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        data = await get_resources(db_client, game_id, host_player["id"], tokens[0])
        assert data["science"] == 6
        assert data["money"] == 2

    async def test_eridani_starting_resources(self, db_client: AsyncClient):
        """Eridani Empire starts with 6 money."""
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["eridani_empire", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        data = await get_resources(db_client, game_id, host_player["id"], tokens[0])
        assert data["money"] == 6

    async def test_starting_population_cubes(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        data = await get_resources(db_client, game_id, host_player["id"], tokens[0])
        cubes = data["population_cubes"]
        assert cubes["orbital"] == 5
        assert cubes["advanced"] == 5
        assert cubes["gauss"] == 5


# ---------------------------------------------------------------------------
# Influence disc tracking
# ---------------------------------------------------------------------------

class TestInfluenceDiscs:
    async def test_non_pass_action_uses_influence_disc(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        # Player 0 takes an EXPLORE action
        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "explore"},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 201

        # One disc should now be in use
        data = await get_resources(db_client, game_id, host_player["id"], tokens[0])
        assert data["influence_discs_used"] == 1
        assert data["influence_discs_remaining"] == 10

    async def test_pass_action_does_not_use_influence_disc(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        # Player 0 passes
        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "pass"},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 201

        # No disc should be used
        data = await get_resources(db_client, game_id, host_player["id"], tokens[0])
        assert data["influence_discs_used"] == 0
        assert data["influence_discs_remaining"] == 11

    async def test_multiple_actions_stack_influence_discs(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        # Player 0 acts, player 1 acts, player 0 acts again (3 total, but p0 acts twice)
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "explore"},
            headers=auth_headers(tokens[0]),
        )
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "explore"},
            headers=auth_headers(tokens[1]),
        )
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "move"},
            headers=auth_headers(tokens[0]),
        )

        data = await get_resources(db_client, game_id, host_player["id"], tokens[0])
        assert data["influence_discs_used"] == 2

    async def test_upkeep_resets_influence_discs(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        # Player 0 uses a disc, then both players pass to enter combat
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "explore"},
            headers=auth_headers(tokens[0]),
        )
        # Player 1's turn; player 1 passes
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "pass"},
            headers=auth_headers(tokens[1]),
        )
        # Player 0 passes (now both have had their actions; p0 already acted once but hasn't passed)
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "pass"},
            headers=auth_headers(tokens[0]),
        )

        # Now in combat phase; advance to upkeep
        await db_client.post(
            f"/games/{game_id}/advance-phase", headers=auth_headers(tokens[0])
        )
        # Advance from upkeep to new round
        await db_client.post(
            f"/games/{game_id}/advance-phase", headers=auth_headers(tokens[0])
        )

        # After upkeep, discs should be reset
        data = await get_resources(db_client, game_id, host_player["id"], tokens[0])
        assert data["influence_discs_used"] == 0
        assert data["influence_discs_remaining"] == 11

    async def test_no_discs_remaining_blocks_action(self, db_session: AsyncSession):
        """Service-level test: use_influence_disc raises ValueError when all discs used."""
        from app.models.player import Player
        from app.models.game import Game, GameStatus
        from app.models.user import User

        # Create minimal DB records
        user = User(email="disc_test@example.com", username="disc_test", hashed_password="x")
        db_session.add(user)
        await db_session.flush()

        game = Game(name="Disc Test", max_players=2, host_user_id=user.id, status=GameStatus.active)
        db_session.add(game)
        await db_session.flush()

        player = Player(game_id=game.id, user_id=user.id, turn_order=0)
        db_session.add(player)
        await db_session.flush()

        # Create resources with all discs used
        resources = PlayerResources(
            player_id=player.id,
            money=5,
            science=5,
            materials=5,
            population_cubes={"orbital": 5, "advanced": 5, "gauss": 5},
            tradespheres=0,
            influence_discs_total=11,
            influence_discs_used=11,  # all used
        )
        db_session.add(resources)
        await db_session.flush()

        with pytest.raises(ValueError, match="No influence discs remaining"):
            await use_influence_disc(player.id, db_session)


# ---------------------------------------------------------------------------
# BUILD cost deduction
# ---------------------------------------------------------------------------

class TestBuildCost:
    async def test_build_interceptor_deducts_materials(self, db_client: AsyncClient):
        """BUILD with ship_type='interceptor' deducts 3 materials."""
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["mechanema", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        # Mechanema starts with 6 materials; interceptor costs 3
        before = await get_resources(db_client, game_id, host_player["id"], tokens[0])
        assert before["materials"] == 6

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "build", "payload": {"ship_type": "interceptor"}},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 201

        after = await get_resources(db_client, game_id, host_player["id"], tokens[0])
        assert after["materials"] == before["materials"] - 3

    async def test_build_cruiser_costs_5_materials(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["mechanema", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "build", "payload": {"ship_type": "cruiser"}},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 201

        after = await get_resources(db_client, game_id, host_player["id"], tokens[0])
        assert after["materials"] == 6 - 5  # Mechanema starts with 6

    async def test_build_fails_with_insufficient_materials(self, db_session: AsyncSession):
        """validate_and_deduct_build_cost raises ValueError when materials < cost."""
        from app.models.player import Player
        from app.models.game import Game, GameStatus
        from app.models.user import User

        user = User(
            email="build_fail@example.com", username="build_fail", hashed_password="x"
        )
        db_session.add(user)
        await db_session.flush()

        game = Game(
            name="Build Test",
            max_players=2,
            host_user_id=user.id,
            status=GameStatus.active,
        )
        db_session.add(game)
        await db_session.flush()

        player = Player(game_id=game.id, user_id=user.id, turn_order=0)
        db_session.add(player)
        await db_session.flush()

        resources = PlayerResources(
            player_id=player.id,
            money=5,
            science=5,
            materials=2,  # not enough for interceptor (costs 3)
            population_cubes={"orbital": 5, "advanced": 5, "gauss": 5},
            tradespheres=0,
            influence_discs_total=11,
            influence_discs_used=0,
        )
        db_session.add(resources)
        await db_session.flush()

        with pytest.raises(ValueError, match="Insufficient materials"):
            await validate_and_deduct_build_cost(player.id, "interceptor", db_session)

    async def test_build_via_api_fails_with_no_materials(self, db_client: AsyncClient):
        """Human player (3 materials) cannot afford a dreadnought (8 materials)."""
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["human", "planta"]
        )
        game_id = game["id"]

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "build", "payload": {"ship_type": "dreadnought"}},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 400
        assert "insufficient" in resp.json()["detail"].lower()

    async def test_build_unknown_ship_type_rejected(self, db_session: AsyncSession):
        from app.models.player import Player
        from app.models.game import Game, GameStatus
        from app.models.user import User

        user = User(email="unk_ship@example.com", username="unk_ship", hashed_password="x")
        db_session.add(user)
        await db_session.flush()

        game = Game(name="Unk", max_players=2, host_user_id=user.id, status=GameStatus.active)
        db_session.add(game)
        await db_session.flush()

        player = Player(game_id=game.id, user_id=user.id, turn_order=0)
        db_session.add(player)
        await db_session.flush()

        resources = PlayerResources(
            player_id=player.id,
            money=5,
            science=5,
            materials=10,
            population_cubes={"orbital": 5, "advanced": 5, "gauss": 5},
            tradespheres=0,
            influence_discs_total=11,
            influence_discs_used=0,
        )
        db_session.add(resources)
        await db_session.flush()

        with pytest.raises(ValueError, match="Unknown ship type"):
            await validate_and_deduct_build_cost(player.id, "battleship", db_session)


# ---------------------------------------------------------------------------
# RESEARCH cost deduction
# ---------------------------------------------------------------------------

class TestResearchCost:
    async def test_research_deducts_science(self, db_session: AsyncSession):
        from app.models.player import Player
        from app.models.game import Game, GameStatus
        from app.models.user import User

        user = User(email="res_sci@example.com", username="res_sci", hashed_password="x")
        db_session.add(user)
        await db_session.flush()

        game = Game(name="Research Test", max_players=2, host_user_id=user.id, status=GameStatus.active)
        db_session.add(game)
        await db_session.flush()

        player = Player(game_id=game.id, user_id=user.id, turn_order=0)
        db_session.add(player)
        await db_session.flush()

        resources = PlayerResources(
            player_id=player.id,
            money=5,
            science=6,
            materials=5,
            population_cubes={"orbital": 5, "advanced": 5, "gauss": 5},
            tradespheres=0,
            influence_discs_total=11,
            influence_discs_used=0,
        )
        db_session.add(resources)
        await db_session.flush()

        await validate_and_deduct_research_cost(player.id, 4, db_session)

        updated = await get_player_resources(player.id, db_session)
        assert updated.science == 2

    async def test_research_fails_with_insufficient_science(self, db_session: AsyncSession):
        from app.models.player import Player
        from app.models.game import Game, GameStatus
        from app.models.user import User

        user = User(email="res_fail@example.com", username="res_fail", hashed_password="x")
        db_session.add(user)
        await db_session.flush()

        game = Game(name="Research Fail", max_players=2, host_user_id=user.id, status=GameStatus.active)
        db_session.add(game)
        await db_session.flush()

        player = Player(game_id=game.id, user_id=user.id, turn_order=0)
        db_session.add(player)
        await db_session.flush()

        resources = PlayerResources(
            player_id=player.id,
            money=5,
            science=2,
            materials=5,
            population_cubes={"orbital": 5, "advanced": 5, "gauss": 5},
            tradespheres=0,
            influence_discs_total=11,
            influence_discs_used=0,
        )
        db_session.add(resources)
        await db_session.flush()

        with pytest.raises(ValueError, match="Insufficient science"):
            await validate_and_deduct_research_cost(player.id, 5, db_session)

    async def test_research_with_science_cost_in_payload(self, db_client: AsyncClient):
        """If payload includes science_cost, science is deducted."""
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["hydran_progress", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        before = await get_resources(db_client, game_id, host_player["id"], tokens[0])
        assert before["science"] == 6  # Hydran starts with 6

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "research", "payload": {"tech_id": "advanced_mining", "science_cost": 3}},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 201

        after = await get_resources(db_client, game_id, host_player["id"], tokens[0])
        assert after["science"] == 3  # 6 - 3

    async def test_research_without_science_cost_does_not_deduct(self, db_client: AsyncClient):
        """Research action without science_cost in payload does not deduct science."""
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["human", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        before = await get_resources(db_client, game_id, host_player["id"], tokens[0])

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "research", "payload": {"tech_id": "advanced_mining"}},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 201

        after = await get_resources(db_client, game_id, host_player["id"], tokens[0])
        assert after["science"] == before["science"]  # unchanged


# ---------------------------------------------------------------------------
# Upkeep calculation
# ---------------------------------------------------------------------------

class TestUpkeepCalculation:
    async def test_upkeep_adds_tradesphere_income(self, db_session: AsyncSession):
        from app.models.player import Player
        from app.models.game import Game, GameStatus
        from app.models.user import User

        user = User(email="trade_up@example.com", username="trade_up", hashed_password="x")
        db_session.add(user)
        await db_session.flush()

        game = Game(name="Trade Upkeep", max_players=2, host_user_id=user.id, status=GameStatus.active)
        db_session.add(game)
        await db_session.flush()

        player = Player(game_id=game.id, user_id=user.id, turn_order=0)
        db_session.add(player)
        await db_session.flush()

        resources = PlayerResources(
            player_id=player.id,
            money=3,
            science=3,
            materials=3,
            population_cubes={"orbital": 5, "advanced": 5, "gauss": 5},
            tradespheres=2,  # 2 tradespheres = 2 money income
            influence_discs_total=11,
            influence_discs_used=3,
        )
        db_session.add(resources)
        await db_session.flush()

        result = await perform_upkeep_for_player(player.id, db_session)

        assert result["money_gained"] == 2
        assert result["bankrupt"] is False

        updated = await get_player_resources(player.id, db_session)
        assert updated.money == 5  # 3 + 2
        assert updated.influence_discs_used == 0  # action discs returned

    async def test_upkeep_with_no_income_does_nothing(self, db_session: AsyncSession):
        from app.models.player import Player
        from app.models.game import Game, GameStatus
        from app.models.user import User

        user = User(email="zero_inc@example.com", username="zero_inc", hashed_password="x")
        db_session.add(user)
        await db_session.flush()

        game = Game(name="Zero Income", max_players=2, host_user_id=user.id, status=GameStatus.active)
        db_session.add(game)
        await db_session.flush()

        player = Player(game_id=game.id, user_id=user.id, turn_order=0)
        db_session.add(player)
        await db_session.flush()

        resources = PlayerResources(
            player_id=player.id,
            money=5,
            science=5,
            materials=5,
            population_cubes={"orbital": 5, "advanced": 5, "gauss": 5},
            tradespheres=0,
            influence_discs_total=11,
            influence_discs_used=4,
        )
        db_session.add(resources)
        await db_session.flush()

        result = await perform_upkeep_for_player(player.id, db_session)

        assert result["money_gained"] == 0
        assert result["bankrupt"] is False
        updated = await get_player_resources(player.id, db_session)
        assert updated.money == 5
        assert updated.influence_discs_used == 0

    async def test_apply_upkeep_for_game_processes_all_players(self, db_session: AsyncSession):
        from app.models.player import Player
        from app.models.game import Game, GameStatus
        from app.models.user import User

        user1 = User(email="up1@example.com", username="up1", hashed_password="x")
        user2 = User(email="up2@example.com", username="up2", hashed_password="x")
        db_session.add_all([user1, user2])
        await db_session.flush()

        game = Game(name="Multi Upkeep", max_players=2, host_user_id=user1.id, status=GameStatus.active)
        db_session.add(game)
        await db_session.flush()

        p1 = Player(game_id=game.id, user_id=user1.id, turn_order=0)
        p2 = Player(game_id=game.id, user_id=user2.id, turn_order=1)
        db_session.add_all([p1, p2])
        await db_session.flush()

        r1 = PlayerResources(
            player_id=p1.id,
            money=3, science=3, materials=3,
            population_cubes={"orbital": 5, "advanced": 5, "gauss": 5},
            tradespheres=1,
            influence_discs_total=11, influence_discs_used=2,
        )
        r2 = PlayerResources(
            player_id=p2.id,
            money=6, science=6, materials=6,
            population_cubes={"orbital": 5, "advanced": 5, "gauss": 5},
            tradespheres=3,
            influence_discs_total=11, influence_discs_used=5,
        )
        db_session.add_all([r1, r2])
        await db_session.flush()

        await apply_upkeep_for_game([p1.id, p2.id], db_session)

        updated_r1 = await get_player_resources(p1.id, db_session)
        updated_r2 = await get_player_resources(p2.id, db_session)

        assert updated_r1.money == 4  # 3 + 1 tradesphere
        assert updated_r1.influence_discs_used == 0
        assert updated_r2.money == 9  # 6 + 3 tradespheres
        assert updated_r2.influence_discs_used == 0


# ---------------------------------------------------------------------------
# GET /games/{id}/players/{id}/resources endpoint
# ---------------------------------------------------------------------------

class TestResourceEndpoint:
    async def test_get_resources_returns_correct_fields(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/resources",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "player_id" in data
        assert "money" in data
        assert "science" in data
        assert "materials" in data
        assert "population_cubes" in data
        assert "tradespheres" in data
        assert "influence_discs_total" in data
        assert "influence_discs_used" in data
        assert "influence_discs_remaining" in data
        assert data["influence_discs_remaining"] == data["influence_discs_total"] - data["influence_discs_used"]

    async def test_get_resources_requires_auth(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/resources"
        )
        assert resp.status_code == 401

    async def test_get_resources_lobby_game_fails(self, db_client: AsyncClient):
        token = await register_and_login(db_client, "lobby_res@example.com", "lobby_res")
        create_resp = await db_client.post(
            "/games",
            json={"name": "Lobby Game", "max_players": 2},
            headers=auth_headers(token),
        )
        game_id = create_resp.json()["id"]
        # player_id doesn't matter much here, just testing the 400
        resp = await db_client.get(
            f"/games/{game_id}/players/1/resources",
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    async def test_get_resources_invalid_player_returns_404(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        resp = await db_client.get(
            f"/games/{game_id}/players/99999/resources",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 404

    async def test_get_resources_invalid_game_returns_404(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        resp = await db_client.get(
            f"/games/99999/players/{host_player['id']}/resources",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 404
