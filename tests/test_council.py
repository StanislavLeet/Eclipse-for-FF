"""Tests for Task 13: Galactic Council & Politics.

Covers:
- Resolution card static data (list, get by id, validate structure)
- CouncilState model creation and defaults
- mark_galactic_center_explored sets flag
- place_ambassadors: valid placement, over-limit rejection, invalid side rejection
- tally_votes: side_a wins, side_b wins, tie
- resolve_vote: VP distributed (1VP per ambassador on winning side), effect applied,
  resolution cleared after vote
- Ambassador placement rejected when no resolution active
- Ambassador placement rejected when GC not explored
- run_council_if_active: returns None when GC not explored, resolves when active
- API: GET /games/{id}/council returns state
- API: POST /games/{id}/council/explore-center marks center explored
- API: POST /games/{id}/council/start-vote starts a vote
- API: POST /games/{id}/council/place-ambassadors places tokens
- API: POST /games/{id}/council/resolve resolves vote
- GET /resolutions returns all resolution cards
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.resolutions import (
    get_resolution,
    get_resolution_ids,
    list_resolutions,
)
from app.models.game import Game, GamePhase, GameStatus
from app.models.player import Player, Species
from app.models.player_resources import PlayerResources
from app.models.user import User
from app.services.council_service import (
    get_or_create_council_state,
    mark_galactic_center_explored,
    place_ambassadors,
    resolve_vote,
    run_council_if_active,
    start_new_vote,
    tally_votes,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SPECIES_CYCLE = [
    "human",
    "planta",
    "mechanema",
    "orion_hegemony",
]


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


async def setup_started_game(
    client: AsyncClient, num_players: int = 2
) -> tuple[list[str], dict]:
    species_list = SPECIES_CYCLE[:num_players]
    tokens = []
    emails = [f"council_p{i}@example.com" for i in range(num_players)]
    usernames = [f"council_player{i}" for i in range(num_players)]

    for i in range(num_players):
        token = await register_and_login(client, emails[i], usernames[i])
        tokens.append(token)

    create_resp = await client.post(
        "/games",
        json={"name": "Council Test Game", "max_players": num_players},
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
# Static data tests
# ---------------------------------------------------------------------------

class TestResolutionData:
    def test_list_resolutions_returns_all(self):
        resolutions = list_resolutions()
        assert len(resolutions) >= 6, "Should have at least 6 resolution cards"

    def test_resolution_ids_are_unique(self):
        ids = get_resolution_ids()
        assert len(ids) == len(set(ids)), "Resolution IDs must be unique"

    def test_get_resolution_returns_card(self):
        card = get_resolution("tax_revenue")
        assert card.resolution_id == "tax_revenue"
        assert card.name == "Tax Revenue"
        assert card.side_a_effect is not None
        assert card.side_b_effect is not None

    def test_get_resolution_raises_on_unknown(self):
        with pytest.raises(KeyError):
            get_resolution("nonexistent_resolution")

    def test_all_resolutions_have_valid_sides(self):
        for card in list_resolutions():
            assert card.side_a_name
            assert card.side_b_name
            assert card.side_a_effect.effect_type in (
                "income_bonus", "vp_bonus", "special", "none"
            )
            assert card.side_b_effect.effect_type in (
                "income_bonus", "vp_bonus", "special", "none"
            )

    def test_all_resolutions_have_categories(self):
        for card in list_resolutions():
            assert card.category is not None


# ---------------------------------------------------------------------------
# CouncilState model and service tests
# ---------------------------------------------------------------------------

class TestCouncilState:
    async def test_create_council_state_defaults(self, db_session: AsyncSession):
        """get_or_create_council_state creates a row with proper defaults."""
        # Need a game row first
        game = Game(
            name="Council Test",
            status=GameStatus.active,
            current_round=1,
            current_phase=GamePhase.upkeep,
            max_players=2,
        )
        db_session.add(game)
        await db_session.flush()

        state = await get_or_create_council_state(db_session, game.id)
        assert state.game_id == game.id
        assert state.galactic_center_explored is False
        assert state.current_resolution_id is None
        assert state.ambassador_placements == {}
        assert state.vp_from_council == {}
        assert state.ambassadors_per_player == 6
        assert state.last_vote_round is None

    async def test_get_or_create_is_idempotent(self, db_session: AsyncSession):
        """Calling get_or_create twice returns the same state."""
        game = Game(
            name="Idempotent Council",
            status=GameStatus.active,
            current_round=1,
            current_phase=GamePhase.upkeep,
            max_players=2,
        )
        db_session.add(game)
        await db_session.flush()

        s1 = await get_or_create_council_state(db_session, game.id)
        s2 = await get_or_create_council_state(db_session, game.id)
        assert s1.id == s2.id

    async def test_mark_galactic_center_explored(self, db_session: AsyncSession):
        game = Game(
            name="GC Explored",
            status=GameStatus.active,
            current_round=1,
            current_phase=GamePhase.upkeep,
            max_players=2,
        )
        db_session.add(game)
        await db_session.flush()

        state = await mark_galactic_center_explored(db_session, game.id)
        assert state.galactic_center_explored is True


# ---------------------------------------------------------------------------
# Ambassador placement tests
# ---------------------------------------------------------------------------

class TestAmbassadorPlacement:
    async def _game_with_players(self, db_session: AsyncSession) -> tuple[Game, list[Player]]:
        """Helper to create an active game with 2 players."""
        user1 = User(email="council_u1@test.com", username="cu1", hashed_password="x")
        user2 = User(email="council_u2@test.com", username="cu2", hashed_password="x")
        db_session.add_all([user1, user2])
        await db_session.flush()

        game = Game(
            name="Placement Test",
            status=GameStatus.active,
            current_round=1,
            current_phase=GamePhase.upkeep,
            max_players=2,
        )
        db_session.add(game)
        await db_session.flush()

        p1 = Player(game_id=game.id, user_id=user1.id, species=Species.human, turn_order=0)
        p2 = Player(game_id=game.id, user_id=user2.id, species=Species.planta, turn_order=1)
        db_session.add_all([p1, p2])
        await db_session.flush()

        return game, [p1, p2]

    async def test_place_ambassadors_on_side_a(self, db_session: AsyncSession):
        game, players = await self._game_with_players(db_session)

        # Mark GC explored and start a vote
        await mark_galactic_center_explored(db_session, game.id)
        await start_new_vote(db_session, game.id, "tax_revenue")

        state = await place_ambassadors(db_session, game.id, players[0].id, "side_a", 3)

        pid = str(players[0].id)
        assert state.ambassador_placements[pid]["side_a"] == 3
        assert state.ambassador_placements[pid].get("side_b", 0) == 0

    async def test_place_ambassadors_split(self, db_session: AsyncSession):
        game, players = await self._game_with_players(db_session)

        await mark_galactic_center_explored(db_session, game.id)
        await start_new_vote(db_session, game.id, "tax_revenue")

        await place_ambassadors(db_session, game.id, players[0].id, "side_a", 2)
        state = await place_ambassadors(db_session, game.id, players[0].id, "side_b", 2)

        pid = str(players[0].id)
        assert state.ambassador_placements[pid]["side_a"] == 2
        assert state.ambassador_placements[pid]["side_b"] == 2

    async def test_place_too_many_ambassadors_raises(self, db_session: AsyncSession):
        game, players = await self._game_with_players(db_session)

        await mark_galactic_center_explored(db_session, game.id)
        await start_new_vote(db_session, game.id, "tax_revenue")

        # ambassadors_per_player == 6, try to place 7
        with pytest.raises(ValueError, match="ambassador"):
            await place_ambassadors(db_session, game.id, players[0].id, "side_a", 7)

    async def test_place_invalid_side_raises(self, db_session: AsyncSession):
        game, players = await self._game_with_players(db_session)

        await mark_galactic_center_explored(db_session, game.id)
        await start_new_vote(db_session, game.id, "tax_revenue")

        with pytest.raises(ValueError, match="side"):
            await place_ambassadors(db_session, game.id, players[0].id, "side_c", 1)

    async def test_place_without_active_resolution_raises(self, db_session: AsyncSession):
        game, players = await self._game_with_players(db_session)
        await mark_galactic_center_explored(db_session, game.id)
        # No vote started — current_resolution_id is None

        with pytest.raises(ValueError, match="No resolution"):
            await place_ambassadors(db_session, game.id, players[0].id, "side_a", 1)

    async def test_place_without_gc_explored_raises(self, db_session: AsyncSession):
        game, players = await self._game_with_players(db_session)
        # GC not explored

        with pytest.raises(ValueError, match="Galactic Center"):
            await place_ambassadors(db_session, game.id, players[0].id, "side_a", 1)


# ---------------------------------------------------------------------------
# Voting tally tests
# ---------------------------------------------------------------------------

class TestTallyVotes:
    def test_side_a_wins(self):
        placements = {
            "1": {"side_a": 4, "side_b": 1},
            "2": {"side_a": 2, "side_b": 2},
        }
        winning_side, side_a_totals, side_b_totals = tally_votes(placements)
        assert winning_side == "side_a"
        assert sum(side_a_totals.values()) == 6
        assert sum(side_b_totals.values()) == 3

    def test_side_b_wins(self):
        placements = {
            "1": {"side_a": 1, "side_b": 5},
            "2": {"side_a": 1, "side_b": 3},
        }
        winning_side, _, _ = tally_votes(placements)
        assert winning_side == "side_b"

    def test_tie_returns_none(self):
        placements = {
            "1": {"side_a": 3},
            "2": {"side_b": 3},
        }
        winning_side, _, _ = tally_votes(placements)
        assert winning_side is None

    def test_empty_placements_is_tie(self):
        winning_side, side_a_totals, side_b_totals = tally_votes({})
        assert winning_side is None
        assert sum(side_a_totals.values()) == 0
        assert sum(side_b_totals.values()) == 0


# ---------------------------------------------------------------------------
# Resolve vote tests
# ---------------------------------------------------------------------------

class TestResolveVote:
    async def _setup(self, db_session: AsyncSession):
        user1 = User(email="rv_u1@test.com", username="rv1", hashed_password="x")
        user2 = User(email="rv_u2@test.com", username="rv2", hashed_password="x")
        db_session.add_all([user1, user2])
        await db_session.flush()

        game = Game(
            name="Resolve Vote Test",
            status=GameStatus.active,
            current_round=1,
            current_phase=GamePhase.upkeep,
            max_players=2,
        )
        db_session.add(game)
        await db_session.flush()

        p1 = Player(game_id=game.id, user_id=user1.id, species=Species.human, turn_order=0, vp_count=0)
        p2 = Player(game_id=game.id, user_id=user2.id, species=Species.planta, turn_order=1, vp_count=0)
        db_session.add_all([p1, p2])
        await db_session.flush()

        # Add resources for both
        r1 = PlayerResources(player_id=p1.id, money=5, science=5, materials=5,
                             population_cubes={}, tradespheres=0,
                             influence_discs_total=11, influence_discs_used=0)
        r2 = PlayerResources(player_id=p2.id, money=5, science=5, materials=5,
                             population_cubes={}, tradespheres=0,
                             influence_discs_total=11, influence_discs_used=0)
        db_session.add_all([r1, r2])
        await db_session.flush()

        return game, [p1, p2], [r1, r2]

    async def test_vp_awarded_per_ambassador_on_winning_side(self, db_session: AsyncSession):
        game, players, resources = await self._setup(db_session)

        await mark_galactic_center_explored(db_session, game.id)
        await start_new_vote(db_session, game.id, "military_pact")

        # p1 places 3 on side_a, p2 places 2 on side_b → side_a wins
        await place_ambassadors(db_session, game.id, players[0].id, "side_a", 3)
        await place_ambassadors(db_session, game.id, players[1].id, "side_b", 2)

        result = await resolve_vote(db_session, game.id, 1)

        assert result["winning_side"] == "side_a"
        # p1 placed 3 ambassadors on winning side → 3 VP
        await db_session.refresh(players[0])
        assert players[0].vp_count == 3 + 1  # +1 from the military_pact vp_bonus effect
        # p2 was on losing side → 0 VP from council
        await db_session.refresh(players[1])
        assert players[1].vp_count == 0

    async def test_resolution_cleared_after_resolve(self, db_session: AsyncSession):
        game, players, _ = await self._setup(db_session)

        await mark_galactic_center_explored(db_session, game.id)
        await start_new_vote(db_session, game.id, "tax_revenue")

        await resolve_vote(db_session, game.id, 1)

        from app.services.council_service import get_council_state
        state = await get_council_state(db_session, game.id)
        assert state.current_resolution_id is None
        assert state.ambassador_placements == {}
        assert state.last_vote_round == 1

    async def test_income_effect_applied_to_winners(self, db_session: AsyncSession):
        game, players, resources = await self._setup(db_session)

        await mark_galactic_center_explored(db_session, game.id)
        await start_new_vote(db_session, game.id, "tax_revenue")

        # p1 places 4 on side_a, p2 places 2 on side_a → side_a wins
        await place_ambassadors(db_session, game.id, players[0].id, "side_a", 4)
        await place_ambassadors(db_session, game.id, players[1].id, "side_a", 4)

        await resolve_vote(db_session, game.id, 1)

        await db_session.refresh(resources[0])
        # tax_revenue side_a effect: +3 money to winners
        assert resources[0].money == 5 + 3

    async def test_tie_no_effect_applied(self, db_session: AsyncSession):
        game, players, resources = await self._setup(db_session)

        await mark_galactic_center_explored(db_session, game.id)
        await start_new_vote(db_session, game.id, "tax_revenue")

        # Equal ambassadors on each side → tie
        await place_ambassadors(db_session, game.id, players[0].id, "side_a", 3)
        await place_ambassadors(db_session, game.id, players[1].id, "side_b", 3)

        result = await resolve_vote(db_session, game.id, 1)

        assert result["winning_side"] is None
        # No VP awarded
        await db_session.refresh(players[0])
        await db_session.refresh(players[1])
        assert players[0].vp_count == 0
        assert players[1].vp_count == 0
        # Money unchanged
        await db_session.refresh(resources[0])
        assert resources[0].money == 5

    async def test_resolve_no_active_resolution_raises(self, db_session: AsyncSession):
        game, players, _ = await self._setup(db_session)
        await mark_galactic_center_explored(db_session, game.id)
        # No vote started

        with pytest.raises(ValueError, match="No active resolution"):
            await resolve_vote(db_session, game.id, 1)


# ---------------------------------------------------------------------------
# run_council_if_active tests
# ---------------------------------------------------------------------------

class TestRunCouncilIfActive:
    async def _setup(self, db_session: AsyncSession):
        user1 = User(email="rcia1@test.com", username="rcia1", hashed_password="x")
        user2 = User(email="rcia2@test.com", username="rcia2", hashed_password="x")
        db_session.add_all([user1, user2])
        await db_session.flush()

        game = Game(
            name="Auto Council",
            status=GameStatus.active,
            current_round=1,
            current_phase=GamePhase.upkeep,
            max_players=2,
        )
        db_session.add(game)
        await db_session.flush()

        p1 = Player(game_id=game.id, user_id=user1.id, species=Species.human, turn_order=0)
        p2 = Player(game_id=game.id, user_id=user2.id, species=Species.planta, turn_order=1)
        db_session.add_all([p1, p2])
        await db_session.flush()

        r1 = PlayerResources(player_id=p1.id, money=3, science=3, materials=3,
                             population_cubes={}, tradespheres=0,
                             influence_discs_total=11, influence_discs_used=0)
        r2 = PlayerResources(player_id=p2.id, money=3, science=3, materials=3,
                             population_cubes={}, tradespheres=0,
                             influence_discs_total=11, influence_discs_used=0)
        db_session.add_all([r1, r2])
        await db_session.flush()

        return game, [p1, p2]

    async def test_returns_none_when_gc_not_explored(self, db_session: AsyncSession):
        game, players = await self._setup(db_session)

        result = await run_council_if_active(db_session, game, [p.id for p in players])
        assert result is None

    async def test_resolves_when_gc_explored(self, db_session: AsyncSession):
        game, players = await self._setup(db_session)

        await mark_galactic_center_explored(db_session, game.id)
        result = await run_council_if_active(db_session, game, [p.id for p in players])
        assert result is not None
        assert "resolution_id" in result
        assert "winning_side" in result

    async def test_does_not_run_twice_in_same_round(self, db_session: AsyncSession):
        game, players = await self._setup(db_session)

        await mark_galactic_center_explored(db_session, game.id)

        result1 = await run_council_if_active(db_session, game, [p.id for p in players])
        assert result1 is not None

        # Second call in same round should return None (already run)
        result2 = await run_council_if_active(db_session, game, [p.id for p in players])
        assert result2 is None


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestCouncilAPI:
    async def test_get_council_state(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        resp = await db_client.get(
            f"/games/{game_id}/council",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["game_id"] == game_id
        assert data["galactic_center_explored"] is False
        assert data["current_resolution_id"] is None

    async def test_list_resolutions_endpoint(self, db_client: AsyncClient):
        tokens, _ = await setup_started_game(db_client, num_players=2)

        resp = await db_client.get(
            "/council/resolutions",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 6
        # Check structure
        card = data[0]
        assert "resolution_id" in card
        assert "side_a_name" in card
        assert "side_b_name" in card

    async def test_mark_gc_explored_endpoint(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        resp = await db_client.post(
            f"/games/{game_id}/council/explore-center",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["galactic_center_explored"] is True

    async def test_start_vote_endpoint(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # First mark GC explored
        await db_client.post(
            f"/games/{game_id}/council/explore-center",
            headers=auth_headers(tokens[0]),
        )

        resp = await db_client.post(
            f"/games/{game_id}/council/start-vote",
            json={"resolution_id": "tax_revenue"},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_resolution_id"] == "tax_revenue"

    async def test_place_ambassadors_endpoint(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        await db_client.post(
            f"/games/{game_id}/council/explore-center",
            headers=auth_headers(tokens[0]),
        )
        await db_client.post(
            f"/games/{game_id}/council/start-vote",
            json={"resolution_id": "tax_revenue"},
            headers=auth_headers(tokens[0]),
        )

        resp = await db_client.post(
            f"/games/{game_id}/council/place-ambassadors",
            json={"side": "side_a", "count": 3},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["side_a_placed"] == 3
        assert data["ambassadors_remaining"] == 3

    async def test_resolve_vote_endpoint(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        await db_client.post(
            f"/games/{game_id}/council/explore-center",
            headers=auth_headers(tokens[0]),
        )
        await db_client.post(
            f"/games/{game_id}/council/start-vote",
            json={"resolution_id": "tax_revenue"},
            headers=auth_headers(tokens[0]),
        )
        await db_client.post(
            f"/games/{game_id}/council/place-ambassadors",
            json={"side": "side_a", "count": 4},
            headers=auth_headers(tokens[0]),
        )

        resp = await db_client.post(
            f"/games/{game_id}/council/resolve",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "resolution_id" in data
        assert "winning_side" in data
        assert "vp_awards" in data

    async def test_place_ambassadors_invalid_side(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        await db_client.post(
            f"/games/{game_id}/council/explore-center",
            headers=auth_headers(tokens[0]),
        )
        await db_client.post(
            f"/games/{game_id}/council/start-vote",
            json={"resolution_id": "tax_revenue"},
            headers=auth_headers(tokens[0]),
        )

        resp = await db_client.post(
            f"/games/{game_id}/council/place-ambassadors",
            json={"side": "invalid_side", "count": 1},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 400

    async def test_start_vote_unknown_resolution(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        await db_client.post(
            f"/games/{game_id}/council/explore-center",
            headers=auth_headers(tokens[0]),
        )

        resp = await db_client.post(
            f"/games/{game_id}/council/start-vote",
            json={"resolution_id": "nonexistent_card"},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 400

    async def test_non_player_cannot_place_ambassadors(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        await db_client.post(
            f"/games/{game_id}/council/explore-center",
            headers=auth_headers(tokens[0]),
        )
        await db_client.post(
            f"/games/{game_id}/council/start-vote",
            json={"resolution_id": "tax_revenue"},
            headers=auth_headers(tokens[0]),
        )

        # Register a third user who is NOT in the game
        outsider_token = await register_and_login(
            db_client, "outsider_council@test.com", "outsider_council"
        )

        resp = await db_client.post(
            f"/games/{game_id}/council/place-ambassadors",
            json={"side": "side_a", "count": 1},
            headers=auth_headers(outsider_token),
        )
        assert resp.status_code == 403
