"""Tests for the turn engine: turn order, action submission, phase transitions."""

from httpx import AsyncClient


# ---- helpers ----------------------------------------------------------------

async def register_and_login(client: AsyncClient, email: str, username: str, password: str = "testpass1") -> str:
    await client.post("/auth/register", json={"email": email, "username": username, "password": password})
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def setup_started_game(client: AsyncClient, num_players: int = 2) -> tuple[list[str], dict]:
    """Create a game with num_players all having species selected, then start it.
    Returns (list of tokens, game dict)."""
    tokens = []
    emails = [f"p{i}@example.com" for i in range(num_players)]
    usernames = [f"player{i}" for i in range(num_players)]
    species = ["human", "planta", "mechanema", "orion_hegemony", "eridani_empire", "hydran_progress"]

    # Register all players
    for i in range(num_players):
        token = await register_and_login(client, emails[i], usernames[i])
        tokens.append(token)

    # Host creates game
    create_resp = await client.post(
        "/games",
        json={"name": "Turn Test Game", "max_players": num_players},
        headers=auth_headers(tokens[0]),
    )
    assert create_resp.status_code == 201
    game = create_resp.json()
    game_id = game["id"]

    # Invite and join remaining players
    for i in range(1, num_players):
        invite_resp = await client.post(
            f"/games/{game_id}/invite",
            json={"invitee_email": emails[i]},
            headers=auth_headers(tokens[0]),
        )
        assert invite_resp.status_code == 201
        invite_token = invite_resp.json()["token"]

        join_resp = await client.post(
            f"/games/{game_id}/join",
            json={"token": invite_token},
            headers=auth_headers(tokens[i]),
        )
        assert join_resp.status_code == 201

    # All players select species
    for i in range(num_players):
        resp = await client.post(
            f"/games/{game_id}/select-species",
            json={"species": species[i]},
            headers=auth_headers(tokens[i]),
        )
        assert resp.status_code == 200

    # Start game
    start_resp = await client.post(f"/games/{game_id}/start", headers=auth_headers(tokens[0]))
    assert start_resp.status_code == 200
    return tokens, start_resp.json()


# ---- turn order -------------------------------------------------------------

class TestTurnOrder:
    async def test_first_player_is_active_on_start(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # Fetch game state
        resp = await db_client.get(f"/games/{game_id}", headers=auth_headers(tokens[0]))
        data = resp.json()
        # First player (turn_order=0) should be active
        active_players = [p for p in data["players"] if p["is_active_turn"]]
        assert len(active_players) == 1

    async def test_turn_advances_after_action(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # First player submits an action (upgrade — no resource cost)
        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={
                "action_type": "upgrade",
                "payload": {"ship_type": "interceptor", "slots": ["nuclear_source", "electron_cannon", "electron_drive", None]},
            },
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 201

        # Now second player should be active
        game_resp = await db_client.get(f"/games/{game_id}", headers=auth_headers(tokens[0]))
        players = game_resp.json()["players"]
        # Find player with turn_order=1
        p1 = next(p for p in players if p["turn_order"] == 1)
        assert p1["is_active_turn"] is True

    async def test_non_active_player_cannot_submit_action(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # Second player (turn_order=1) tries to act first — should fail
        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={
                "action_type": "upgrade",
                "payload": {"ship_type": "interceptor", "slots": ["nuclear_source", "electron_cannon", "electron_drive", None]},
            },
            headers=auth_headers(tokens[1]),
        )
        assert resp.status_code == 400
        assert "not your turn" in resp.json()["detail"].lower()

    async def test_non_player_cannot_submit_action(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # Register an outsider
        outsider_token = await register_and_login(db_client, "outsider@example.com", "outsider")
        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={
                "action_type": "upgrade",
                "payload": {"ship_type": "interceptor", "slots": ["nuclear_source", "electron_cannon", "electron_drive", None]},
            },
            headers=auth_headers(outsider_token),
        )
        assert resp.status_code == 403


# ---- pass and phase transition -----------------------------------------------

class TestPassAndPhaseTransition:
    async def test_pass_marks_player_as_passed(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # Player 0 passes
        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "pass"},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 201
        assert resp.json()["action_type"] == "pass"

    async def test_all_pass_triggers_combat_phase(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # Player 0 passes
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "pass"},
            headers=auth_headers(tokens[0]),
        )
        # Player 1 passes
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "pass"},
            headers=auth_headers(tokens[1]),
        )

        # Game should now be in combat phase
        game_resp = await db_client.get(f"/games/{game_id}", headers=auth_headers(tokens[0]))
        assert game_resp.json()["current_phase"] == "combat"

    async def test_combat_to_upkeep_phase_transition(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # Both players pass to enter combat
        for token in tokens:
            await db_client.post(
                f"/games/{game_id}/action",
                json={"action_type": "pass"},
                headers=auth_headers(token),
            )

        # Host advances from combat to upkeep
        resp = await db_client.post(
            f"/games/{game_id}/advance-phase",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        assert resp.json()["current_phase"] == "upkeep"

    async def test_upkeep_to_new_round_transition(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # Advance through combat and upkeep
        for token in tokens:
            await db_client.post(
                f"/games/{game_id}/action",
                json={"action_type": "pass"},
                headers=auth_headers(token),
            )
        # combat phase
        await db_client.post(f"/games/{game_id}/advance-phase", headers=auth_headers(tokens[0]))
        # upkeep phase -> new round
        await db_client.post(f"/games/{game_id}/advance-phase", headers=auth_headers(tokens[0]))

        game_resp = await db_client.get(f"/games/{game_id}", headers=auth_headers(tokens[0]))
        data = game_resp.json()
        assert data["current_round"] == 2
        assert data["current_phase"] == "activation"

    async def test_player_cannot_act_after_passing(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # Player 0 passes
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "pass"},
            headers=auth_headers(tokens[0]),
        )

        # Player 1 takes an action (moves turn back to... wait, player 0 has passed so turn stays on player 1)
        # Actually after player 0 passes, player 1 is active. Player 1 acts.
        await db_client.post(
            f"/games/{game_id}/action",
            json={
                "action_type": "upgrade",
                "payload": {"ship_type": "interceptor", "slots": ["nuclear_source", "electron_cannon", "electron_drive", None]},
            },
            headers=auth_headers(tokens[1]),
        )

        # Now it would be player 0's turn again, but player 0 already passed.
        # So it should wrap to player 1 again (only active non-passed player).
        # Player 0 tries to act - should fail (has passed)
        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "pass"},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 400

    async def test_non_host_cannot_advance_phase(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # Both pass to enter combat
        for token in tokens:
            await db_client.post(
                f"/games/{game_id}/action",
                json={"action_type": "pass"},
                headers=auth_headers(token),
            )

        # Non-host tries to advance phase
        resp = await db_client.post(
            f"/games/{game_id}/advance-phase",
            headers=auth_headers(tokens[1]),
        )
        assert resp.status_code == 403

    async def test_cannot_advance_activation_phase_manually(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # Game is in activation phase; host tries to advance
        resp = await db_client.post(
            f"/games/{game_id}/advance-phase",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 400
        assert "activation" in resp.json()["detail"].lower()


# ---- action history ---------------------------------------------------------

class TestActionHistory:
    async def test_get_actions_empty(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        resp = await db_client.get(
            f"/games/{game_id}/actions",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_actions_after_submit(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # Submit a couple of actions
        await db_client.post(
            f"/games/{game_id}/action",
            json={
                "action_type": "upgrade",
                "payload": {"ship_type": "interceptor", "slots": ["nuclear_source", "electron_cannon", "electron_drive", None]},
            },
            headers=auth_headers(tokens[0]),
        )
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "pass"},
            headers=auth_headers(tokens[1]),
        )

        resp = await db_client.get(
            f"/games/{game_id}/actions",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        actions = resp.json()
        assert len(actions) == 2
        assert actions[0]["action_type"] == "upgrade"
        assert actions[1]["action_type"] == "pass"

    async def test_action_has_correct_fields(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "research", "payload": {"tech_id": "advanced_mining"}},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["action_type"] == "research"
        assert data["round_number"] == 1
        assert data["payload"] == {"tech_id": "advanced_mining"}
        assert "timestamp" in data

    async def test_get_actions_lobby_game_fails(self, db_client: AsyncClient):
        token = await register_and_login(db_client, "lobbyact@example.com", "lobbyact")
        create_resp = await db_client.post(
            "/games",
            json={"name": "Lobby Game", "max_players": 2},
            headers=auth_headers(token),
        )
        game_id = create_resp.json()["id"]

        resp = await db_client.get(
            f"/games/{game_id}/actions",
            headers=auth_headers(token),
        )
        assert resp.status_code == 400


# ---- 3-player turn rotation -------------------------------------------------

class TestThreePlayerTurnRotation:
    async def test_three_player_turn_order(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=3)
        game_id = game["id"]

        # Turn should go p0 -> p1 -> p2 -> p0 -> ...
        for expected_turn in range(3):
            # Check the active player
            game_resp = await db_client.get(f"/games/{game_id}", headers=auth_headers(tokens[0]))
            players = game_resp.json()["players"]
            active = [p for p in players if p["is_active_turn"]]
            assert len(active) == 1
            assert active[0]["turn_order"] == expected_turn

            # Submit upgrade action (no resource cost, works for all species)
            resp = await db_client.post(
                f"/games/{game_id}/action",
                json={
                    "action_type": "upgrade",
                    "payload": {"ship_type": "interceptor", "slots": ["nuclear_source", "electron_cannon", "electron_drive", None]},
                },
                headers=auth_headers(tokens[expected_turn]),
            )
            assert resp.status_code == 201

    async def test_three_player_all_pass(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=3)
        game_id = game["id"]

        # All three players pass in order
        for i in range(3):
            resp = await db_client.post(
                f"/games/{game_id}/action",
                json={"action_type": "pass"},
                headers=auth_headers(tokens[i]),
            )
            assert resp.status_code == 201

        # Game should be in combat phase
        game_resp = await db_client.get(f"/games/{game_id}", headers=auth_headers(tokens[0]))
        assert game_resp.json()["current_phase"] == "combat"
