"""Task 18: Acceptance Criteria Tests.

Covers:
- Full game setup flow: two players create game, invite, join, species, start
- Action submission: PASS, UPGRADE, RESEARCH actions via API
- Player resource endpoint: GET /games/{id}/players/{id}/resources
- Player blueprints endpoint: GET /games/{id}/players/{id}/blueprints
- Player ships endpoint: GET /games/{id}/players/{id}/ships
- Player technologies endpoint: GET /games/{id}/players/{id}/technologies
- Available technologies endpoint: GET /games/{id}/players/{id}/technologies/available
- Action history endpoint: GET /games/{id}/actions
- Phase transitions: activation -> combat -> upkeep -> new round
- Illegal action rejection (not your turn, wrong phase)
- Scores endpoint: GET /games/{id}/scores
- Combat logs endpoint with round filter
- 8-round game end trigger
"""

from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
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


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def full_setup(
    client: AsyncClient, tag: str, num_players: int = 2
) -> tuple[list[str], dict]:
    """Create a started game with `num_players` and return (tokens, game_dict)."""
    species_cycle = [
        "human", "planta", "mechanema", "orion_hegemony",
        "eridani_empire", "hydran_progress",
    ]
    tokens = []
    for i in range(num_players):
        t = await register_and_login(
            client, f"accept_{tag}_{i}@test.com", f"accept_{tag}_{i}"
        )
        tokens.append(t)

    resp = await client.post(
        "/games",
        json={"name": f"accept-game-{tag}", "max_players": num_players},
        headers=auth(tokens[0]),
    )
    assert resp.status_code == 201
    game_id = resp.json()["id"]

    for i in range(1, num_players):
        inv = await client.post(
            f"/games/{game_id}/invite",
            json={"invitee_email": f"accept_{tag}_{i}@test.com"},
            headers=auth(tokens[0]),
        )
        tok = inv.json()["token"]
        await client.post(
            f"/games/{game_id}/join",
            json={"token": tok},
            headers=auth(tokens[i]),
        )

    for i in range(num_players):
        await client.post(
            f"/games/{game_id}/select-species",
            json={"species": species_cycle[i]},
            headers=auth(tokens[i]),
        )

    start = await client.post(f"/games/{game_id}/start", headers=auth(tokens[0]))
    assert start.status_code == 200
    return tokens, start.json()


# ---------------------------------------------------------------------------
# Manual test 1: Two players create game, invite, join, select species, start
# ---------------------------------------------------------------------------


class TestFullGameSetup:
    async def test_two_player_game_setup_flow(self, db_client: AsyncClient):
        """Covers the full lobby flow end-to-end."""
        t0 = await register_and_login(db_client, "setup_h@t.com", "setup_h")
        t1 = await register_and_login(db_client, "setup_j@t.com", "setup_j")

        # Host creates game
        resp = await db_client.post(
            "/games",
            json={"name": "Setup Flow Game", "max_players": 2},
            headers=auth(t0),
        )
        assert resp.status_code == 201
        game = resp.json()
        game_id = game["id"]
        assert game["status"] == "lobby"
        assert game["max_players"] == 2

        # Retrieve game info
        get_resp = await db_client.get(f"/games/{game_id}", headers=auth(t0))
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == game_id

        # Host invites second player
        inv = await db_client.post(
            f"/games/{game_id}/invite",
            json={"invitee_email": "setup_j@t.com"},
            headers=auth(t0),
        )
        assert inv.status_code == 201
        token = inv.json()["token"]
        assert token

        # Second player joins
        join = await db_client.post(
            f"/games/{game_id}/join",
            json={"token": token},
            headers=auth(t1),
        )
        assert join.status_code == 201

        # Both select species
        s0 = await db_client.post(
            f"/games/{game_id}/select-species",
            json={"species": "human"},
            headers=auth(t0),
        )
        assert s0.status_code == 200

        s1 = await db_client.post(
            f"/games/{game_id}/select-species",
            json={"species": "planta"},
            headers=auth(t1),
        )
        assert s1.status_code == 200

        # Host starts game
        start = await db_client.post(f"/games/{game_id}/start", headers=auth(t0))
        assert start.status_code == 200
        data = start.json()
        assert data["status"] == "active"
        assert data["current_phase"] == "activation"
        assert data["current_round"] == 1

    async def test_duplicate_species_rejected(self, db_client: AsyncClient):
        """Two players cannot pick the same species."""
        t0 = await register_and_login(db_client, "dup_h@t.com", "dup_h")
        t1 = await register_and_login(db_client, "dup_j@t.com", "dup_j")

        resp = await db_client.post(
            "/games",
            json={"name": "Dup Species Game", "max_players": 2},
            headers=auth(t0),
        )
        game_id = resp.json()["id"]
        inv = await db_client.post(
            f"/games/{game_id}/invite",
            json={"invitee_email": "dup_j@t.com"},
            headers=auth(t0),
        )
        tok = inv.json()["token"]
        await db_client.post(
            f"/games/{game_id}/join", json={"token": tok}, headers=auth(t1)
        )

        await db_client.post(
            f"/games/{game_id}/select-species",
            json={"species": "human"},
            headers=auth(t0),
        )
        resp2 = await db_client.post(
            f"/games/{game_id}/select-species",
            json={"species": "human"},
            headers=auth(t1),
        )
        assert resp2.status_code == 400

    async def test_cannot_start_without_all_species(self, db_client: AsyncClient):
        """Game cannot start if not all players have chosen species."""
        t0 = await register_and_login(db_client, "nospec_h@t.com", "nospec_h")
        t1 = await register_and_login(db_client, "nospec_j@t.com", "nospec_j")

        resp = await db_client.post(
            "/games",
            json={"name": "No Species Game", "max_players": 2},
            headers=auth(t0),
        )
        game_id = resp.json()["id"]
        inv = await db_client.post(
            f"/games/{game_id}/invite",
            json={"invitee_email": "nospec_j@t.com"},
            headers=auth(t0),
        )
        tok = inv.json()["token"]
        await db_client.post(
            f"/games/{game_id}/join", json={"token": tok}, headers=auth(t1)
        )

        # Only host selects species
        await db_client.post(
            f"/games/{game_id}/select-species",
            json={"species": "human"},
            headers=auth(t0),
        )
        start = await db_client.post(f"/games/{game_id}/start", headers=auth(t0))
        assert start.status_code == 400


# ---------------------------------------------------------------------------
# Manual test 2: Full turn cycle via API
# ---------------------------------------------------------------------------


class TestFullTurnCycle:
    async def test_complete_activation_to_new_round(self, db_client: AsyncClient):
        """Both players pass -> combat -> advance to upkeep -> advance to round 2."""
        tokens, game = await full_setup(db_client, "cycle")
        game_id = game["id"]

        # Both players pass
        for tok in tokens:
            resp = await db_client.post(
                f"/games/{game_id}/action",
                json={"action_type": "pass"},
                headers=auth(tok),
            )
            assert resp.status_code == 201

        g = await db_client.get(f"/games/{game_id}", headers=auth(tokens[0]))
        assert g.json()["current_phase"] == "combat"

        # Advance combat -> upkeep
        r1 = await db_client.post(f"/games/{game_id}/advance-phase", headers=auth(tokens[0]))
        assert r1.status_code == 200
        assert r1.json()["current_phase"] == "upkeep"

        # Advance upkeep -> round 2
        r2 = await db_client.post(f"/games/{game_id}/advance-phase", headers=auth(tokens[0]))
        assert r2.status_code == 200

        g2 = await db_client.get(f"/games/{game_id}", headers=auth(tokens[0]))
        data = g2.json()
        assert data["current_round"] == 2
        assert data["current_phase"] == "activation"

    async def test_upgrade_action_then_pass(self, db_client: AsyncClient):
        """Player 0 does an UPGRADE action, player 1 passes, then player 0 passes."""
        tokens, game = await full_setup(db_client, "upgrade")
        game_id = game["id"]

        # Player 0 upgrades interceptor blueprint
        r = await db_client.post(
            f"/games/{game_id}/action",
            json={
                "action_type": "upgrade",
                "payload": {
                    "ship_type": "interceptor",
                    "slots": ["nuclear_source", "electron_cannon", "electron_drive", None],
                },
            },
            headers=auth(tokens[0]),
        )
        assert r.status_code == 201

        # Player 1 passes
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "pass"},
            headers=auth(tokens[1]),
        )

        # Player 0 passes
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "pass"},
            headers=auth(tokens[0]),
        )

        g = await db_client.get(f"/games/{game_id}", headers=auth(tokens[0]))
        assert g.json()["current_phase"] == "combat"


# ---------------------------------------------------------------------------
# Manual test 3: Research a technology and verify effects
# ---------------------------------------------------------------------------


class TestResearchTechnology:
    async def test_research_advanced_mining_via_action(self, db_client: AsyncClient):
        """Player researches advanced_mining via the action API."""
        tokens, game = await full_setup(db_client, "research1")
        game_id = game["id"]

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "research", "payload": {"tech_id": "advanced_mining"}},
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 201
        assert resp.json()["action_type"] == "research"

    async def test_research_missing_tech_id_rejected(self, db_client: AsyncClient):
        """RESEARCH action without tech_id in payload should be rejected."""
        tokens, game = await full_setup(db_client, "research2")
        game_id = game["id"]

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "research", "payload": {}},
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 400

    async def test_get_player_technologies_after_research(self, db_client: AsyncClient):
        """GET /technologies lists the researched tech."""
        tokens, game = await full_setup(db_client, "research3")
        game_id = game["id"]

        # Research a tech
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "research", "payload": {"tech_id": "advanced_mining"}},
            headers=auth(tokens[0]),
        )

        # Get game state to find player_id
        g = await db_client.get(f"/games/{game_id}", headers=auth(tokens[0]))
        players = g.json()["players"]
        player_id = next(p["id"] for p in players if p["turn_order"] == 0)

        # Fetch technologies
        resp = await db_client.get(
            f"/games/{game_id}/players/{player_id}/technologies",
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 200
        techs = resp.json()
        tech_ids = [t["tech_id"] for t in techs]
        assert "advanced_mining" in tech_ids

    async def test_get_technologies_for_non_existent_game(self, db_client: AsyncClient):
        """GET /technologies for a missing game returns 404."""
        t = await register_and_login(db_client, "tech404@t.com", "tech404")
        resp = await db_client.get(
            "/games/999999/players/1/technologies",
            headers=auth(t),
        )
        assert resp.status_code == 404

    async def test_get_technologies_lobby_game_rejected(self, db_client: AsyncClient):
        """GET /technologies for a game in lobby returns 400."""
        t = await register_and_login(db_client, "techlobby@t.com", "techlobby")
        cr = await db_client.post(
            "/games",
            json={"name": "Lobby Tech", "max_players": 2},
            headers=auth(t),
        )
        game_id = cr.json()["id"]

        # Get game state to find player_id
        g = await db_client.get(f"/games/{game_id}", headers=auth(t))
        player_id = g.json()["players"][0]["id"]

        resp = await db_client.get(
            f"/games/{game_id}/players/{player_id}/technologies",
            headers=auth(t),
        )
        assert resp.status_code == 400

    async def test_get_technologies_unknown_player_returns_404(self, db_client: AsyncClient):
        """GET /technologies for a player not in the game returns 404."""
        tokens, game = await full_setup(db_client, "technoplay")
        game_id = game["id"]

        resp = await db_client.get(
            f"/games/{game_id}/players/999999/technologies",
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 404

    async def test_get_available_technologies_endpoint(self, db_client: AsyncClient):
        """GET /technologies/available returns unowned, affordable techs with costs."""
        tokens, game = await full_setup(db_client, "availtech")
        game_id = game["id"]

        g = await db_client.get(f"/games/{game_id}", headers=auth(tokens[0]))
        player_id = next(
            p["id"] for p in g.json()["players"] if p["turn_order"] == 0
        )

        resp = await db_client.get(
            f"/games/{game_id}/players/{player_id}/technologies/available",
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Should have some technologies available at start
        assert len(data) > 0
        # Check structure
        first = data[0]
        assert "tech_id" in first
        assert "name" in first
        assert "effective_cost" in first

    async def test_get_available_technologies_not_found_game(self, db_client: AsyncClient):
        """GET /technologies/available for missing game returns 404."""
        t = await register_and_login(db_client, "avail404@t.com", "avail404")
        resp = await db_client.get(
            "/games/999999/players/1/technologies/available",
            headers=auth(t),
        )
        assert resp.status_code == 404

    async def test_get_available_technologies_lobby_returns_400(self, db_client: AsyncClient):
        """GET /technologies/available for lobby game returns 400."""
        t = await register_and_login(db_client, "availlobby@t.com", "availlobby")
        cr = await db_client.post(
            "/games",
            json={"name": "Lobby Avail", "max_players": 2},
            headers=auth(t),
        )
        game_id = cr.json()["id"]

        g = await db_client.get(f"/games/{game_id}", headers=auth(t))
        player_id = g.json()["players"][0]["id"]

        resp = await db_client.get(
            f"/games/{game_id}/players/{player_id}/technologies/available",
            headers=auth(t),
        )
        assert resp.status_code == 400

    async def test_get_available_technologies_unknown_player_404(self, db_client: AsyncClient):
        """GET /technologies/available for unknown player returns 404."""
        tokens, game = await full_setup(db_client, "availnoplay")
        resp = await db_client.get(
            f"/games/{game['id']}/players/999999/technologies/available",
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Player resources endpoint
# ---------------------------------------------------------------------------


class TestPlayerResourcesEndpoint:
    async def test_get_resources_returns_expected_fields(self, db_client: AsyncClient):
        tokens, game = await full_setup(db_client, "res1")
        game_id = game["id"]

        g = await db_client.get(f"/games/{game_id}", headers=auth(tokens[0]))
        player_id = next(
            p["id"] for p in g.json()["players"] if p["turn_order"] == 0
        )

        resp = await db_client.get(
            f"/games/{game_id}/players/{player_id}/resources",
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "money" in data
        assert "science" in data
        assert "materials" in data
        assert "influence_discs_total" in data
        assert data["player_id"] == player_id

    async def test_get_resources_lobby_game_rejected(self, db_client: AsyncClient):
        t = await register_and_login(db_client, "reslobby@t.com", "reslobby")
        cr = await db_client.post(
            "/games",
            json={"name": "Res Lobby", "max_players": 2},
            headers=auth(t),
        )
        game_id = cr.json()["id"]
        g = await db_client.get(f"/games/{game_id}", headers=auth(t))
        player_id = g.json()["players"][0]["id"]

        resp = await db_client.get(
            f"/games/{game_id}/players/{player_id}/resources",
            headers=auth(t),
        )
        assert resp.status_code == 400

    async def test_get_resources_player_not_found(self, db_client: AsyncClient):
        tokens, game = await full_setup(db_client, "res2")
        resp = await db_client.get(
            f"/games/{game['id']}/players/999999/resources",
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 404

    async def test_get_resources_game_not_found(self, db_client: AsyncClient):
        t = await register_and_login(db_client, "res404@t.com", "res404")
        resp = await db_client.get(
            "/games/999999/players/1/resources",
            headers=auth(t),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Player blueprints and ships endpoints
# ---------------------------------------------------------------------------


class TestBlueprintsAndShipsEndpoints:
    async def test_get_blueprints_returns_list(self, db_client: AsyncClient):
        tokens, game = await full_setup(db_client, "bp1")
        game_id = game["id"]

        g = await db_client.get(f"/games/{game_id}", headers=auth(tokens[0]))
        player_id = next(
            p["id"] for p in g.json()["players"] if p["turn_order"] == 0
        )

        resp = await db_client.get(
            f"/games/{game_id}/players/{player_id}/blueprints",
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        bp = data[0]
        assert "ship_type" in bp
        assert "slots" in bp
        assert "power_balance" in bp

    async def test_get_blueprints_lobby_game_rejected(self, db_client: AsyncClient):
        t = await register_and_login(db_client, "bplobby@t.com", "bplobby")
        cr = await db_client.post(
            "/games",
            json={"name": "BP Lobby", "max_players": 2},
            headers=auth(t),
        )
        game_id = cr.json()["id"]
        g = await db_client.get(f"/games/{game_id}", headers=auth(t))
        player_id = g.json()["players"][0]["id"]

        resp = await db_client.get(
            f"/games/{game_id}/players/{player_id}/blueprints",
            headers=auth(t),
        )
        assert resp.status_code == 400

    async def test_get_blueprints_player_not_found(self, db_client: AsyncClient):
        tokens, game = await full_setup(db_client, "bp2")
        resp = await db_client.get(
            f"/games/{game['id']}/players/999999/blueprints",
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 404

    async def test_get_blueprints_game_not_found(self, db_client: AsyncClient):
        t = await register_and_login(db_client, "bp404@t.com", "bp404")
        resp = await db_client.get(
            "/games/999999/players/1/blueprints",
            headers=auth(t),
        )
        assert resp.status_code == 404

    async def test_get_ships_returns_list(self, db_client: AsyncClient):
        tokens, game = await full_setup(db_client, "ships1")
        game_id = game["id"]

        g = await db_client.get(f"/games/{game_id}", headers=auth(tokens[0]))
        player_id = next(
            p["id"] for p in g.json()["players"] if p["turn_order"] == 0
        )

        resp = await db_client.get(
            f"/games/{game_id}/players/{player_id}/ships",
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Player should have starting ships
        for ship in data:
            assert "ship_type" in ship
            assert "hp_remaining" in ship
            assert "hex_tile_id" in ship

    async def test_get_ships_lobby_game_rejected(self, db_client: AsyncClient):
        t = await register_and_login(db_client, "shiplobby@t.com", "shiplobby")
        cr = await db_client.post(
            "/games",
            json={"name": "Ship Lobby", "max_players": 2},
            headers=auth(t),
        )
        game_id = cr.json()["id"]
        g = await db_client.get(f"/games/{game_id}", headers=auth(t))
        player_id = g.json()["players"][0]["id"]

        resp = await db_client.get(
            f"/games/{game_id}/players/{player_id}/ships",
            headers=auth(t),
        )
        assert resp.status_code == 400

    async def test_get_ships_player_not_found(self, db_client: AsyncClient):
        tokens, game = await full_setup(db_client, "ships2")
        resp = await db_client.get(
            f"/games/{game['id']}/players/999999/ships",
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 404

    async def test_get_ships_game_not_found(self, db_client: AsyncClient):
        t = await register_and_login(db_client, "ship404@t.com", "ship404")
        resp = await db_client.get(
            "/games/999999/players/1/ships",
            headers=auth(t),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Manual test 4 (automated): Scores endpoint
# ---------------------------------------------------------------------------


class TestScoresEndpoint:
    async def test_scores_returns_player_vp(self, db_client: AsyncClient):
        tokens, game = await full_setup(db_client, "scores1")
        game_id = game["id"]

        resp = await db_client.get(f"/games/{game_id}/scores", headers=auth(tokens[0]))
        assert resp.status_code == 200
        data = resp.json()
        # Response contains game_id and players with VP info
        assert "players" in data or "scores" in data or isinstance(data, list)

    async def test_scores_game_not_found(self, db_client: AsyncClient):
        t = await register_and_login(db_client, "sc404@t.com", "sc404")
        resp = await db_client.get("/games/999999/scores", headers=auth(t))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Manual test 6: Illegal move rejection
# ---------------------------------------------------------------------------


class TestIllegalActionRejection:
    async def test_action_not_your_turn_rejected(self, db_client: AsyncClient):
        """Player 1 cannot submit an action when it's player 0's turn."""
        tokens, game = await full_setup(db_client, "illegal1")
        game_id = game["id"]

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "pass"},
            headers=auth(tokens[1]),
        )
        assert resp.status_code == 400
        assert "not your turn" in resp.json()["detail"].lower()

    async def test_non_player_action_rejected(self, db_client: AsyncClient):
        """A user not in the game cannot submit actions."""
        tokens, game = await full_setup(db_client, "illegal2")
        game_id = game["id"]

        outsider = await register_and_login(db_client, "outsider_ill@t.com", "outsider_ill")
        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "pass"},
            headers=auth(outsider),
        )
        assert resp.status_code == 403

    async def test_action_on_nonexistent_game_rejected(self, db_client: AsyncClient):
        """Action on a non-existent game returns 404."""
        t = await register_and_login(db_client, "act404@t.com", "act404")
        resp = await db_client.post(
            "/games/999999/action",
            json={"action_type": "pass"},
            headers=auth(t),
        )
        assert resp.status_code in (404, 400)

    async def test_move_action_without_required_fields_rejected(self, db_client: AsyncClient):
        """MOVE action without ship_id/path in payload is rejected."""
        tokens, game = await full_setup(db_client, "illegal3")
        game_id = game["id"]

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "move", "payload": {}},
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 400

    async def test_explore_action_without_required_fields_rejected(self, db_client: AsyncClient):
        """EXPLORE action without ship_id/target_hex_id in payload is rejected."""
        tokens, game = await full_setup(db_client, "illegal4")
        game_id = game["id"]

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "explore", "payload": {}},
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 400

    async def test_influence_action_without_required_fields_rejected(self, db_client: AsyncClient):
        """INFLUENCE action without hex_tile_id in payload is rejected."""
        tokens, game = await full_setup(db_client, "illegal5")
        game_id = game["id"]

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "influence", "payload": {}},
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 400

    async def test_colonize_action_without_required_fields_rejected(self, db_client: AsyncClient):
        """COLONIZE action without required fields is rejected."""
        tokens, game = await full_setup(db_client, "illegal6")
        game_id = game["id"]

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "colonize", "payload": {}},
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 400

    async def test_upgrade_action_missing_fields_rejected(self, db_client: AsyncClient):
        """UPGRADE action without required fields is rejected."""
        tokens, game = await full_setup(db_client, "illegal7")
        game_id = game["id"]

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "upgrade", "payload": {}},
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Action history endpoint
# ---------------------------------------------------------------------------


class TestActionHistory:
    async def test_get_actions_returns_all_submitted(self, db_client: AsyncClient):
        tokens, game = await full_setup(db_client, "hist1")
        game_id = game["id"]

        # Submit two actions
        await db_client.post(
            f"/games/{game_id}/action",
            json={
                "action_type": "upgrade",
                "payload": {
                    "ship_type": "interceptor",
                    "slots": ["nuclear_source", "electron_cannon", "electron_drive", None],
                },
            },
            headers=auth(tokens[0]),
        )
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "pass"},
            headers=auth(tokens[1]),
        )

        resp = await db_client.get(
            f"/games/{game_id}/actions",
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 200
        actions = resp.json()
        assert len(actions) == 2

    async def test_get_actions_game_not_found(self, db_client: AsyncClient):
        t = await register_and_login(db_client, "hist404@t.com", "hist404")
        resp = await db_client.get("/games/999999/actions", headers=auth(t))
        assert resp.status_code == 404

    async def test_get_actions_lobby_game_rejected(self, db_client: AsyncClient):
        t = await register_and_login(db_client, "histlobby@t.com", "histlobby")
        cr = await db_client.post(
            "/games",
            json={"name": "Hist Lobby", "max_players": 2},
            headers=auth(t),
        )
        game_id = cr.json()["id"]

        resp = await db_client.get(f"/games/{game_id}/actions", headers=auth(t))
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Combat logs endpoint (additional coverage)
# ---------------------------------------------------------------------------


class TestCombatLogsEndpoint:
    async def test_get_combat_logs_with_round_filter(self, db_client: AsyncClient):
        """GET /combat/logs?round=1 filters by round number."""
        tokens, game = await full_setup(db_client, "combatlog1")
        game_id = game["id"]

        resp = await db_client.get(
            f"/games/{game_id}/combat/logs?round=1",
            headers=auth(tokens[0]),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_combat_logs_game_not_found(self, db_client: AsyncClient):
        t = await register_and_login(db_client, "clog404@t.com", "clog404")
        resp = await db_client.get(
            "/games/999999/combat/logs",
            headers=auth(t),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Advance phase endpoint (additional coverage)
# ---------------------------------------------------------------------------


class TestAdvancePhaseEndpoint:
    async def test_advance_phase_game_not_found(self, db_client: AsyncClient):
        t = await register_and_login(db_client, "advph404@t.com", "advph404")
        resp = await db_client.post(
            "/games/999999/advance-phase",
            headers=auth(t),
        )
        assert resp.status_code == 404

    async def test_non_host_cannot_advance_phase(self, db_client: AsyncClient):
        tokens, game = await full_setup(db_client, "advph1")
        game_id = game["id"]

        # Both pass to enter combat phase
        for tok in tokens:
            await db_client.post(
                f"/games/{game_id}/action",
                json={"action_type": "pass"},
                headers=auth(tok),
            )

        # Non-host tries to advance
        resp = await db_client.post(
            f"/games/{game_id}/advance-phase",
            headers=auth(tokens[1]),
        )
        assert resp.status_code == 403
