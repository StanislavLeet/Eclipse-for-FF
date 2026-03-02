"""Tests for email notifications and the GET /games/{id}/status endpoint."""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient


# ---- helpers -----------------------------------------------------------------

async def register_and_login(
    client: AsyncClient,
    email: str,
    username: str,
    password: str = "testpass1",
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
) -> tuple[list[str], list[str], dict]:
    """Create + start a game; return (tokens, emails, game_dict)."""
    tokens: list[str] = []
    emails = [f"notif{i}@example.com" for i in range(num_players)]
    usernames = [f"notifuser{i}" for i in range(num_players)]
    species = ["human", "planta", "mechanema", "orion_hegemony"]

    for i in range(num_players):
        token = await register_and_login(client, emails[i], usernames[i])
        tokens.append(token)

    create_resp = await client.post(
        "/games",
        json={"name": "Notif Test Game", "max_players": num_players},
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
        assert invite_resp.status_code == 201
        inv_token = invite_resp.json()["token"]
        join_resp = await client.post(
            f"/games/{game_id}/join",
            json={"token": inv_token},
            headers=auth_headers(tokens[i]),
        )
        assert join_resp.status_code == 201

    for i in range(num_players):
        resp = await client.post(
            f"/games/{game_id}/select-species",
            json={"species": species[i]},
            headers=auth_headers(tokens[i]),
        )
        assert resp.status_code == 200

    start_resp = await client.post(
        f"/games/{game_id}/start", headers=auth_headers(tokens[0])
    )
    assert start_resp.status_code == 200
    return tokens, emails, start_resp.json()


# ---- game status endpoint ----------------------------------------------------

class TestGameStatusEndpoint:
    async def test_status_returns_correct_fields(self, db_client: AsyncClient):
        tokens, emails, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        resp = await db_client.get(
            f"/games/{game_id}/status", headers=auth_headers(tokens[0])
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["id"] == game_id
        assert data["name"] == "Notif Test Game"
        assert data["status"] == "active"
        assert data["current_round"] == 1
        assert data["current_phase"] == "activation"
        assert data["active_player_id"] is not None

    async def test_status_active_player_matches_game_state(self, db_client: AsyncClient):
        tokens, emails, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        status_resp = await db_client.get(
            f"/games/{game_id}/status", headers=auth_headers(tokens[0])
        )
        game_resp = await db_client.get(
            f"/games/{game_id}", headers=auth_headers(tokens[0])
        )

        status_data = status_resp.json()
        game_data = game_resp.json()

        active_players = [p for p in game_data["players"] if p["is_active_turn"]]
        assert len(active_players) == 1
        assert status_data["active_player_id"] == active_players[0]["id"]

    async def test_status_404_for_unknown_game(self, db_client: AsyncClient):
        tokens, _, _ = await setup_started_game(db_client, num_players=2)
        resp = await db_client.get(
            "/games/99999/status", headers=auth_headers(tokens[0])
        )
        assert resp.status_code == 404

    async def test_status_requires_auth(self, db_client: AsyncClient):
        tokens, _, game = await setup_started_game(db_client, num_players=2)
        resp = await db_client.get(f"/games/{game['id']}/status")
        assert resp.status_code == 401


# ---- notify_game_started -----------------------------------------------------

class TestNotifyGameStarted:
    async def test_send_email_called_for_each_player_on_start(self, db_client: AsyncClient):
        with patch(
            "app.services.notification_service.send_email",
            new_callable=AsyncMock,
        ) as mock_send:
            tokens, emails, game = await setup_started_game(db_client, num_players=2)

        # One email per player (2-player game)
        assert mock_send.call_count == 2
        called_tos = [c.args[0] for c in mock_send.call_args_list]
        for email in emails:
            assert email in called_tos

    async def test_game_start_email_contains_game_link(self, db_client: AsyncClient):
        with patch(
            "app.services.notification_service.send_email",
            new_callable=AsyncMock,
        ) as mock_send:
            tokens, emails, game = await setup_started_game(db_client, num_players=2)

        # Check that at least one call's body contains the game link
        game_id = game["id"]
        bodies = [c.args[2] for c in mock_send.call_args_list]
        assert any(f"/games/{game_id}" in body for body in bodies)

    async def test_game_start_email_mentions_game_name(self, db_client: AsyncClient):
        with patch(
            "app.services.notification_service.send_email",
            new_callable=AsyncMock,
        ) as mock_send:
            tokens, emails, game = await setup_started_game(db_client, num_players=2)

        subjects = [c.args[1] for c in mock_send.call_args_list]
        assert any("Notif Test Game" in s for s in subjects)


# ---- notify_turn_change ------------------------------------------------------

class TestNotifyTurnChange:
    async def test_send_email_called_on_turn_change(self, db_client: AsyncClient):
        tokens, emails, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        with patch(
            "app.services.notification_service.send_email",
            new_callable=AsyncMock,
        ) as mock_send:
            # First player submits PASS action → turn moves to second player
            resp = await db_client.post(
                f"/games/{game_id}/action",
                json={"action_type": "pass"},
                headers=auth_headers(tokens[0]),
            )
            assert resp.status_code == 201

        # Exactly one email should be sent to the next player
        assert mock_send.call_count == 1

    async def test_turn_change_email_contains_game_link(self, db_client: AsyncClient):
        tokens, emails, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        with patch(
            "app.services.notification_service.send_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await db_client.post(
                f"/games/{game_id}/action",
                json={"action_type": "pass"},
                headers=auth_headers(tokens[0]),
            )

        bodies = [c.args[2] for c in mock_send.call_args_list]
        assert any(f"/games/{game_id}" in body for body in bodies)

    async def test_turn_change_email_recipient_is_next_player(self, db_client: AsyncClient):
        tokens, emails, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # Determine which player is active (player 0 or player 1)
        status_resp = await db_client.get(
            f"/games/{game_id}/status", headers=auth_headers(tokens[0])
        )
        active_player_id = status_resp.json()["active_player_id"]
        game_resp = await db_client.get(
            f"/games/{game_id}", headers=auth_headers(tokens[0])
        )
        players = game_resp.json()["players"]
        active_idx = next(i for i, p in enumerate(players) if p["id"] == active_player_id)
        inactive_idx = 1 - active_idx  # with 2 players
        next_email = emails[inactive_idx]

        with patch(
            "app.services.notification_service.send_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await db_client.post(
                f"/games/{game_id}/action",
                json={"action_type": "pass"},
                headers=auth_headers(tokens[active_idx]),
            )

        called_tos = [c.args[0] for c in mock_send.call_args_list]
        assert next_email in called_tos


# ---- notify_game_ended (unit test of the service function) ------------------

class TestNotifyGameEnded:
    async def test_notify_game_ended_sends_to_all_players(self, db_session):
        """Unit test: call notify_game_ended directly and verify send_email calls."""
        from app.models.game import Game, GamePhase, GameStatus
        from app.models.player import Player, Species
        from app.models.user import User
        from app.services.notification_service import notify_game_ended

        # Create minimal user + game + player records in the test DB
        user1 = User(email="end1@example.com", username="enduser1", hashed_password="x")
        user2 = User(email="end2@example.com", username="enduser2", hashed_password="x")
        db_session.add_all([user1, user2])
        await db_session.flush()

        game = Game(
            name="Finished Game",
            status=GameStatus.finished,
            current_round=8,
            current_phase=GamePhase.upkeep,
            max_players=2,
            host_user_id=user1.id,
        )
        db_session.add(game)
        await db_session.flush()

        p1 = Player(game_id=game.id, user_id=user1.id, turn_order=0, vp_count=15, species=Species.human)
        p2 = Player(game_id=game.id, user_id=user2.id, turn_order=1, vp_count=10, species=Species.planta)
        db_session.add_all([p1, p2])
        await db_session.flush()

        with patch(
            "app.services.notification_service.send_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await notify_game_ended(db_session, game, [p1, p2], winner=p1)

        assert mock_send.call_count == 2
        called_tos = {c.args[0] for c in mock_send.call_args_list}
        assert "end1@example.com" in called_tos
        assert "end2@example.com" in called_tos

    async def test_notify_game_ended_email_mentions_winner(self, db_session):
        from app.models.game import Game, GamePhase, GameStatus
        from app.models.player import Player, Species
        from app.models.user import User
        from app.services.notification_service import notify_game_ended

        user = User(email="winner@example.com", username="winneruser", hashed_password="x")
        db_session.add(user)
        await db_session.flush()

        game = Game(
            name="Win Game",
            status=GameStatus.finished,
            current_round=8,
            current_phase=GamePhase.upkeep,
            max_players=2,
            host_user_id=user.id,
        )
        db_session.add(game)
        await db_session.flush()

        p = Player(game_id=game.id, user_id=user.id, turn_order=0, vp_count=20, species=Species.human)
        db_session.add(p)
        await db_session.flush()

        with patch(
            "app.services.notification_service.send_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await notify_game_ended(db_session, game, [p], winner=p)

        bodies = [c.args[2] for c in mock_send.call_args_list]
        assert any("winner@example.com" in body or "20 VP" in body for body in bodies)


# ---- send_email (unit test of the sender) ------------------------------------

class TestSendEmailUnit:
    async def test_send_email_skipped_when_smtp_not_configured(self):
        """When smtp_host is empty, send_email should not raise and should skip sending."""
        from app.config import settings
        from app.tasks.email_sender import send_email

        original = settings.smtp_host
        settings.smtp_host = ""
        try:
            # Should not raise
            await send_email("user@example.com", "Test", "Body")
        finally:
            settings.smtp_host = original

    async def test_send_email_error_is_caught_and_logged(self):
        """Even if the sync SMTP call fails, send_email should not propagate the error."""
        from app.tasks.email_sender import send_email

        def broken_sync(*args):
            raise ConnectionRefusedError("No SMTP server")

        with patch(
            "app.tasks.email_sender._send_email_sync",
            side_effect=broken_sync,
        ):
            # Should not raise
            await send_email("user@example.com", "Test", "Body")
