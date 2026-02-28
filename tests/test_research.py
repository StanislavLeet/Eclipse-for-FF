"""Tests for Task 8: Technology Research Tree.

Covers:
- Technology definitions: all categories populated, costs, prerequisites
- Prerequisite enforcement: cannot research without prerequisites
- Cost calculation with category discounts
- Duplicate acquisition rejection
- Ancient (discovery-only) tech cannot be researched
- RESEARCH action via POST /games/{id}/action
- GET /games/{id}/players/{id}/technologies endpoint
- GET /games/{id}/players/{id}/technologies/available endpoint
- Immediate tech effect application (flat bonuses)
- Insufficient science rejection
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.technologies import (
    TechCategory,
    get_technology,
    list_researchable_technologies,
    list_technologies,
    list_technologies_by_category,
)
from app.services.research_service import (
    apply_research,
    calculate_effective_cost,
    count_techs_in_category,
    get_player_tech_ids,
    grant_technology,
    validate_research,
)


# ---------------------------------------------------------------------------
# Shared helpers
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
    emails = [f"rsch_p{i}@example.com" for i in range(num_players)]
    usernames = [f"rsch_player{i}" for i in range(num_players)]

    for i in range(num_players):
        token = await register_and_login(client, emails[i], usernames[i])
        tokens.append(token)

    create_resp = await client.post(
        "/games",
        json={"name": "Research Test Game", "max_players": num_players},
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


# ---------------------------------------------------------------------------
# Technology data definitions
# ---------------------------------------------------------------------------

class TestTechnologyDefinitions:
    def test_all_six_categories_populated(self):
        for cat in TechCategory:
            techs = list_technologies_by_category(cat)
            assert len(techs) >= 1, f"Category {cat.value} has no technologies"

    def test_military_techs_exist(self):
        mil = list_technologies_by_category(TechCategory.military)
        ids = {t.tech_id for t in mil}
        assert "improved_hull" in ids
        assert "gauss_shield" in ids
        assert "neural_targeting" in ids

    def test_grid_techs_exist(self):
        grid = list_technologies_by_category(TechCategory.grid)
        ids = {t.tech_id for t in grid}
        assert "nuclear_drive" in ids
        assert "fusion_drive" in ids
        assert "nuclear_source" in ids

    def test_nano_techs_exist(self):
        nano = list_technologies_by_category(TechCategory.nano)
        ids = {t.tech_id for t in nano}
        assert "advanced_mining" in ids
        assert "quantum_grid" in ids

    def test_quantum_techs_exist(self):
        q = list_technologies_by_category(TechCategory.quantum)
        ids = {t.tech_id for t in q}
        assert "ion_cannon" in ids
        assert "flux_missile" in ids

    def test_rare_techs_exist(self):
        rare = list_technologies_by_category(TechCategory.rare)
        ids = {t.tech_id for t in rare}
        assert "cloaking_device" in ids
        assert "point_defense" in ids

    def test_ancient_techs_exist(self):
        anc = list_technologies_by_category(TechCategory.ancient)
        assert len(anc) >= 1

    def test_ancient_techs_not_researchable(self):
        anc = list_technologies_by_category(TechCategory.ancient)
        for t in anc:
            assert not t.can_research, f"{t.name} should have can_research=False"

    def test_researchable_list_excludes_ancient(self):
        researchable = list_researchable_technologies()
        for t in researchable:
            assert t.category != TechCategory.ancient

    def test_get_technology_by_id(self):
        tech = get_technology("ion_cannon")
        assert tech.name == "Ion Cannon"
        assert tech.category == TechCategory.quantum
        assert tech.base_cost == 2

    def test_get_technology_unknown_raises(self):
        with pytest.raises(KeyError):
            get_technology("nonexistent_tech_xyz")

    def test_prerequisites_are_valid_tech_ids(self):
        all_ids = {t.tech_id for t in list_technologies()}
        for tech in list_technologies():
            for prereq_id in tech.prerequisites:
                assert prereq_id in all_ids, (
                    f"Tech '{tech.tech_id}' references unknown prereq '{prereq_id}'"
                )

    def test_all_techs_have_at_least_one_effect(self):
        for tech in list_technologies():
            assert len(tech.effects) >= 1, f"Tech '{tech.tech_id}' has no effects"

    def test_base_costs_are_non_negative(self):
        for tech in list_technologies():
            assert tech.base_cost >= 0, f"Tech '{tech.tech_id}' has negative base cost"


# ---------------------------------------------------------------------------
# Cost calculation with category discounts
# ---------------------------------------------------------------------------

class TestCostCalculation:
    def test_no_discount_with_zero_owned(self):
        tech = get_technology("ion_cannon")  # base_cost=2
        assert calculate_effective_cost(tech, 0) == 2

    def test_discount_reduces_cost_by_one_per_owned(self):
        tech = get_technology("ion_cannon")  # base_cost=2
        assert calculate_effective_cost(tech, 1) == 1
        assert calculate_effective_cost(tech, 2) == 0

    def test_cost_never_below_zero(self):
        tech = get_technology("ion_cannon")  # base_cost=2
        assert calculate_effective_cost(tech, 10) == 0

    def test_expensive_tech_discount(self):
        tech = get_technology("antimatter_cannon")  # base_cost=9
        assert calculate_effective_cost(tech, 3) == 6
        assert calculate_effective_cost(tech, 9) == 0

    async def test_count_techs_in_category_empty(self, db_session: AsyncSession):
        # Insert a player directly for unit test
        from app.models.player import Player, Species
        from app.models.game import Game, GameStatus, GamePhase
        from app.models.user import User

        user = User(email="costtest@example.com", username="costtest", hashed_password="x")
        db_session.add(user)
        await db_session.flush()

        game = Game(
            name="cost-test",
            status=GameStatus.active,
            max_players=2,
            current_round=1,
            current_phase=GamePhase.activation,
            host_user_id=user.id,
        )
        db_session.add(game)
        await db_session.flush()

        player = Player(
            game_id=game.id,
            user_id=user.id,
            species=Species.human,
            turn_order=0,
        )
        db_session.add(player)
        await db_session.flush()

        count = await count_techs_in_category(player.id, TechCategory.quantum, db_session)
        assert count == 0

    async def test_count_techs_in_category_after_grants(self, db_session: AsyncSession):
        from app.models.player import Player, Species
        from app.models.game import Game, GameStatus, GamePhase
        from app.models.user import User
        from app.models.player_resources import PlayerResources

        user = User(email="catcount@example.com", username="catcount", hashed_password="x")
        db_session.add(user)
        await db_session.flush()

        game = Game(
            name="catcount-test",
            status=GameStatus.active,
            max_players=2,
            current_round=1,
            current_phase=GamePhase.activation,
            host_user_id=user.id,
        )
        db_session.add(game)
        await db_session.flush()

        player = Player(
            game_id=game.id,
            user_id=user.id,
            species=Species.human,
            turn_order=0,
        )
        db_session.add(player)
        await db_session.flush()

        resources = PlayerResources(
            player_id=player.id, money=10, science=10, materials=10
        )
        db_session.add(resources)
        await db_session.flush()

        # Grant two quantum techs
        await grant_technology(player.id, "ion_cannon", 1, db_session)
        await grant_technology(player.id, "flux_missile", 1, db_session)

        count = await count_techs_in_category(player.id, TechCategory.quantum, db_session)
        assert count == 2


# ---------------------------------------------------------------------------
# Research validation
# ---------------------------------------------------------------------------

class TestResearchValidation:
    async def _make_player(self, db, email_suffix, science=20):
        from app.models.player import Player, Species
        from app.models.game import Game, GameStatus, GamePhase
        from app.models.user import User
        from app.models.player_resources import PlayerResources

        user = User(
            email=f"valtest_{email_suffix}@example.com",
            username=f"valtest_{email_suffix}",
            hashed_password="x",
        )
        db.add(user)
        await db.flush()

        game = Game(
            name=f"val-test-{email_suffix}",
            status=GameStatus.active,
            max_players=2,
            current_round=1,
            current_phase=GamePhase.activation,
            host_user_id=user.id,
        )
        db.add(game)
        await db.flush()

        player = Player(
            game_id=game.id,
            user_id=user.id,
            species=Species.human,
            turn_order=0,
        )
        db.add(player)
        await db.flush()

        resources = PlayerResources(
            player_id=player.id, money=10, science=science, materials=10
        )
        db.add(resources)
        await db.flush()

        return player, resources

    async def test_validate_research_success(self, db_session: AsyncSession):
        player, _ = await self._make_player(db_session, "vr01")
        tech, cost = await validate_research(player.id, "ion_cannon", db_session)
        assert tech.tech_id == "ion_cannon"
        assert cost == 2  # base cost, 0 owned in category

    async def test_cannot_research_ancient_tech(self, db_session: AsyncSession):
        player, _ = await self._make_player(db_session, "vr02")
        with pytest.raises(ValueError, match="cannot be researched"):
            await validate_research(player.id, "monolith", db_session)

    async def test_prerequisite_not_met(self, db_session: AsyncSession):
        player, _ = await self._make_player(db_session, "vr03")
        # plasma_cannon requires ion_cannon
        with pytest.raises(ValueError, match="prerequisite"):
            await validate_research(player.id, "plasma_cannon", db_session)

    async def test_prerequisite_met_after_grant(self, db_session: AsyncSession):
        player, _ = await self._make_player(db_session, "vr04")
        # Grant the prerequisite
        await grant_technology(player.id, "ion_cannon", 1, db_session)
        tech, cost = await validate_research(player.id, "plasma_cannon", db_session)
        assert tech.tech_id == "plasma_cannon"
        # With 1 owned in quantum category, cost = 6 - 1 = 5
        assert cost == 5

    async def test_duplicate_tech_rejected(self, db_session: AsyncSession):
        player, _ = await self._make_player(db_session, "vr05")
        await grant_technology(player.id, "ion_cannon", 1, db_session)
        with pytest.raises(ValueError, match="already owns"):
            await validate_research(player.id, "ion_cannon", db_session)

    async def test_unknown_tech_id_rejected(self, db_session: AsyncSession):
        player, _ = await self._make_player(db_session, "vr06")
        with pytest.raises(ValueError, match="Unknown technology"):
            await validate_research(player.id, "totally_fake_tech", db_session)


# ---------------------------------------------------------------------------
# apply_research (science deduction + acquisition)
# ---------------------------------------------------------------------------

class TestApplyResearch:
    async def _make_player(self, db, email_suffix, science=20):
        from app.models.player import Player, Species
        from app.models.game import Game, GameStatus, GamePhase
        from app.models.user import User
        from app.models.player_resources import PlayerResources

        user = User(
            email=f"applytest_{email_suffix}@example.com",
            username=f"applytest_{email_suffix}",
            hashed_password="x",
        )
        db.add(user)
        await db.flush()

        game = Game(
            name=f"apply-test-{email_suffix}",
            status=GameStatus.active,
            max_players=2,
            current_round=1,
            current_phase=GamePhase.activation,
            host_user_id=user.id,
        )
        db.add(game)
        await db.flush()

        player = Player(
            game_id=game.id,
            user_id=user.id,
            species=Species.human,
            turn_order=0,
        )
        db.add(player)
        await db.flush()

        resources = PlayerResources(
            player_id=player.id, money=10, science=science, materials=10
        )
        db.add(resources)
        await db.flush()

        return player, resources

    async def test_apply_research_deducts_science(self, db_session: AsyncSession):
        player, resources = await self._make_player(db_session, "ar01", science=10)
        await apply_research(player.id, "ion_cannon", 1, db_session)
        # ion_cannon costs 2 science, 10 - 2 = 8
        assert resources.science == 8

    async def test_apply_research_records_acquisition(self, db_session: AsyncSession):
        player, _ = await self._make_player(db_session, "ar02", science=10)
        record = await apply_research(player.id, "improved_hull", 1, db_session)
        assert record.player_id == player.id
        assert record.tech_id == "improved_hull"
        assert record.acquired_round == 1

    async def test_apply_research_insufficient_science(self, db_session: AsyncSession):
        player, _ = await self._make_player(db_session, "ar03", science=1)
        # ion_cannon costs 2, player only has 1
        with pytest.raises(ValueError, match="Insufficient science"):
            await apply_research(player.id, "ion_cannon", 1, db_session)

    async def test_apply_research_discount_reduces_cost(self, db_session: AsyncSession):
        player, resources = await self._make_player(db_session, "ar04", science=15)
        # Grant ion_cannon first (quantum, base cost 2)
        await grant_technology(player.id, "ion_cannon", 1, db_session)
        science_before = resources.science
        # flux_missile has base_cost=3, discount 1 (1 owned in quantum) => effective cost=2
        await apply_research(player.id, "flux_missile", 1, db_session)
        assert resources.science == science_before - 2

    async def test_apply_research_zero_cost_possible(self, db_session: AsyncSession):
        player, resources = await self._make_player(db_session, "ar05", science=15)
        # ion_cannon (base 2), flux_missile (base 3), positron_computer (base 3)
        # After owning 2 quantum techs, positron_computer costs 3-2=1
        await grant_technology(player.id, "ion_cannon", 1, db_session)
        await grant_technology(player.id, "flux_missile", 1, db_session)
        science_before = resources.science
        await apply_research(player.id, "positron_computer", 1, db_session)
        # 3 - 2 = 1
        assert resources.science == science_before - 1

    async def test_apply_research_owned_added_to_player_tech_ids(
        self, db_session: AsyncSession
    ):
        player, _ = await self._make_player(db_session, "ar06", science=20)
        await apply_research(player.id, "nuclear_drive", 1, db_session)
        ids = await get_player_tech_ids(player.id, db_session)
        assert "nuclear_drive" in ids

    async def test_prospector_grant_adds_money_immediately(self, db_session: AsyncSession):
        """Ancient tech Prospector grants money immediately when granted."""
        player, resources = await self._make_player(db_session, "ar07")
        money_before = resources.money
        await grant_technology(player.id, "prospector", 1, db_session)
        # prospector gives 3 money immediately (once=True, flat=3)
        assert resources.money == money_before + 3


# ---------------------------------------------------------------------------
# RESEARCH action via the API
# ---------------------------------------------------------------------------

class TestResearchActionAPI:
    async def test_research_action_success(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # Human starts with 3 science; ion_cannon costs 2
        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "research", "payload": {"tech_id": "ion_cannon"}},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["action_type"] == "research"
        assert data["payload"]["tech_id"] == "ion_cannon"

    async def test_research_without_tech_id_rejected(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(
            db_client,
            num_players=2,
            species_list=["human", "planta"],
        )
        game_id = game["id"]

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "research", "payload": {}},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 400
        assert "tech_id" in resp.json()["detail"]

    async def test_research_insufficient_science_rejected(self, db_client: AsyncClient):
        # Planta starts with 3 science, antimatter_cannon costs 9+ → insufficient
        tokens, game = await setup_started_game(
            db_client,
            num_players=2,
            species_list=["planta", "human"],
        )
        game_id = game["id"]

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={
                "action_type": "research",
                "payload": {"tech_id": "antimatter_cannon"},
            },
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 400

    async def test_research_missing_prerequisite_rejected(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # plasma_cannon requires ion_cannon
        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "research", "payload": {"tech_id": "plasma_cannon"}},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 400
        assert "prerequisite" in resp.json()["detail"].lower()

    async def test_research_ancient_tech_rejected(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "research", "payload": {"tech_id": "monolith"}},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 400
        assert "cannot be researched" in resp.json()["detail"].lower()

    async def test_research_deducts_science_visible_in_resources(
        self, db_client: AsyncClient
    ):
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["human", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        # human starts with 3 science; ion_cannon costs 2 → should have 1 left
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "research", "payload": {"tech_id": "ion_cannon"}},
            headers=auth_headers(tokens[0]),
        )
        res_resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/resources",
            headers=auth_headers(tokens[0]),
        )
        assert res_resp.status_code == 200
        assert res_resp.json()["science"] == 1


# ---------------------------------------------------------------------------
# GET /games/{id}/players/{id}/technologies endpoint
# ---------------------------------------------------------------------------

class TestTechnologiesEndpoint:
    async def test_empty_technologies_on_game_start(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/technologies",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_technologies_listed_after_research(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["human", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "research", "payload": {"tech_id": "ion_cannon"}},
            headers=auth_headers(tokens[0]),
        )

        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/technologies",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        techs = resp.json()
        assert len(techs) == 1
        assert techs[0]["tech_id"] == "ion_cannon"
        assert techs[0]["tech_name"] == "Ion Cannon"
        assert techs[0]["category"] == "quantum"
        assert techs[0]["acquired_round"] == 1

    async def test_technologies_endpoint_requires_auth(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/technologies"
        )
        assert resp.status_code == 401

    async def test_technologies_404_for_invalid_game(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)

        resp = await db_client.get(
            "/games/99999/players/1/technologies",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 404

    async def test_technologies_404_for_invalid_player(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        resp = await db_client.get(
            f"/games/{game_id}/players/99999/technologies",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 404

    async def test_technologies_400_for_lobby_game(self, db_client: AsyncClient):
        tokens = []
        for i in range(2):
            t = await register_and_login(
                db_client, f"lobby_rsch_{i}@example.com", f"lobbyrsch{i}"
            )
            tokens.append(t)

        create_resp = await db_client.post(
            "/games",
            json={"name": "Lobby Research Game", "max_players": 2},
            headers=auth_headers(tokens[0]),
        )
        game_id = create_resp.json()["id"]

        # Join but don't start
        invite_resp = await db_client.post(
            f"/games/{game_id}/invite",
            json={"invitee_email": "lobby_rsch_1@example.com"},
            headers=auth_headers(tokens[0]),
        )
        invite_token = invite_resp.json()["token"]
        await db_client.post(
            f"/games/{game_id}/join",
            json={"token": invite_token},
            headers=auth_headers(tokens[1]),
        )

        resp = await db_client.get(
            f"/games/{game_id}/players/1/technologies",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET available technologies endpoint
# ---------------------------------------------------------------------------

class TestAvailableTechnologiesEndpoint:
    async def test_available_techs_excludes_owned(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["human", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        # Research ion_cannon
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "research", "payload": {"tech_id": "ion_cannon"}},
            headers=auth_headers(tokens[0]),
        )

        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/technologies/available",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        available_ids = {t["tech_id"] for t in resp.json()}
        assert "ion_cannon" not in available_ids

    async def test_available_techs_excludes_ancient(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/technologies/available",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        for tech in resp.json():
            assert tech["category"] != "ancient"

    async def test_available_techs_excludes_prereq_not_met(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/technologies/available",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        available_ids = {t["tech_id"] for t in resp.json()}
        # plasma_cannon requires ion_cannon — should not be available at start
        assert "plasma_cannon" not in available_ids

    async def test_available_techs_shows_effective_cost(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["human", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/technologies/available",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        ion = next((t for t in resp.json() if t["tech_id"] == "ion_cannon"), None)
        assert ion is not None
        assert ion["effective_cost"] == 2  # base cost, no discount yet
        assert ion["base_cost"] == 2

    async def test_available_techs_discount_applies_after_research(
        self, db_client: AsyncClient
    ):
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["hydran_progress", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        # hydran_progress starts with 6 science
        # Research ion_cannon (cost 2) → 4 science left
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "research", "payload": {"tech_id": "ion_cannon"}},
            headers=auth_headers(tokens[0]),
        )

        # Now flux_missile available (no prereq, base cost 3, discount 1 = effective 2)
        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/technologies/available",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        flux = next((t for t in resp.json() if t["tech_id"] == "flux_missile"), None)
        assert flux is not None
        assert flux["effective_cost"] == 2  # base 3, discount 1
