from httpx import AsyncClient


# ---- helpers ----------------------------------------------------------------

async def register_and_login(client: AsyncClient, email: str, username: str, password: str = "pass123") -> str:
    await client.post("/auth/register", json={"email": email, "username": username, "password": password})
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def create_game(client: AsyncClient, token: str, name: str = "Test Game", max_players: int = 4) -> dict:
    resp = await client.post(
        "/games",
        json={"name": name, "max_players": max_players},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---- species list -----------------------------------------------------------

class TestSpeciesList:
    async def test_list_species_unauthenticated(self, db_client: AsyncClient):
        resp = await db_client.get("/games/species")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 9
        names = [s["name"] for s in data]
        assert "Human" in names
        assert "Eridani Empire" in names
        assert "Mechanema" in names

    async def test_species_have_required_fields(self, db_client: AsyncClient):
        resp = await db_client.get("/games/species")
        for species in resp.json():
            assert "species_id" in species
            assert "name" in species
            assert "description" in species
            assert "starting_money" in species
            assert "starting_science" in species
            assert "starting_materials" in species
            assert "homeworld_slots" in species
            assert "starting_ships" in species
            assert "special_ability" in species


# ---- game creation ----------------------------------------------------------

class TestCreateGame:
    async def test_create_game_success(self, db_client: AsyncClient):
        token = await register_and_login(db_client, "host@example.com", "host")
        game = await create_game(db_client, token)
        assert game["name"] == "Test Game"
        assert game["max_players"] == 4
        assert game["status"] == "lobby"
        assert game["host_user_id"] is not None
        assert len(game["players"]) == 1  # host auto-joins

    async def test_create_game_unauthenticated(self, db_client: AsyncClient):
        resp = await db_client.post("/games", json={"name": "NoAuth Game"})
        assert resp.status_code == 401

    async def test_create_game_invalid_max_players_too_low(self, db_client: AsyncClient):
        token = await register_and_login(db_client, "host2@example.com", "host2")
        resp = await db_client.post(
            "/games",
            json={"name": "Bad Game", "max_players": 1},
            headers=auth_headers(token),
        )
        assert resp.status_code == 422

    async def test_create_game_invalid_max_players_too_high(self, db_client: AsyncClient):
        token = await register_and_login(db_client, "host3@example.com", "host3")
        resp = await db_client.post(
            "/games",
            json={"name": "Bad Game", "max_players": 7},
            headers=auth_headers(token),
        )
        assert resp.status_code == 422


# ---- list games -------------------------------------------------------------

class TestListGames:
    async def test_list_games_success(self, db_client: AsyncClient):
        token = await register_and_login(db_client, "lg1@example.com", "lguser1")
        await create_game(db_client, token, name="Lobby One")

        resp = await db_client.get("/games", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Lobby One"

    async def test_list_games_only_returns_games_for_current_user(self, db_client: AsyncClient):
        token_a = await register_and_login(db_client, "lg2a@example.com", "lguser2a")
        token_b = await register_and_login(db_client, "lg2b@example.com", "lguser2b")

        await create_game(db_client, token_a, name="A Game")
        await create_game(db_client, token_b, name="B Game")

        resp_a = await db_client.get("/games", headers=auth_headers(token_a))
        assert resp_a.status_code == 200
        names_a = [g["name"] for g in resp_a.json()]
        assert names_a == ["A Game"]

        resp_b = await db_client.get("/games", headers=auth_headers(token_b))
        assert resp_b.status_code == 200
        names_b = [g["name"] for g in resp_b.json()]
        assert names_b == ["B Game"]

    async def test_list_games_unauthenticated(self, db_client: AsyncClient):
        resp = await db_client.get("/games")
        assert resp.status_code == 401


# ---- get game ---------------------------------------------------------------

class TestGetGame:
    async def test_get_game_success(self, db_client: AsyncClient):
        token = await register_and_login(db_client, "g@example.com", "guser")
        game = await create_game(db_client, token, name="My Game")
        resp = await db_client.get(f"/games/{game['id']}", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "My Game"

    async def test_get_game_not_found(self, db_client: AsyncClient):
        token = await register_and_login(db_client, "g2@example.com", "guser2")
        resp = await db_client.get("/games/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_get_game_unauthenticated(self, db_client: AsyncClient):
        token = await register_and_login(db_client, "g3@example.com", "guser3")
        game = await create_game(db_client, token)
        resp = await db_client.get(f"/games/{game['id']}")
        assert resp.status_code == 401


# ---- invite flow ------------------------------------------------------------

class TestInvite:
    async def test_invite_success(self, db_client: AsyncClient):
        token = await register_and_login(db_client, "ihost@example.com", "ihost")
        game = await create_game(db_client, token)
        resp = await db_client.post(
            f"/games/{game['id']}/invite",
            json={"invitee_email": "invited@example.com"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["invitee_email"] == "invited@example.com"
        assert "token" in data
        assert data["accepted"] is False

    async def test_invite_non_host_forbidden(self, db_client: AsyncClient):
        host_token = await register_and_login(db_client, "ihost2@example.com", "ihost2")
        other_token = await register_and_login(db_client, "other@example.com", "otheruser")
        game = await create_game(db_client, host_token)
        resp = await db_client.post(
            f"/games/{game['id']}/invite",
            json={"invitee_email": "victim@example.com"},
            headers=auth_headers(other_token),
        )
        assert resp.status_code == 403

    async def test_invite_game_not_found(self, db_client: AsyncClient):
        token = await register_and_login(db_client, "ihost3@example.com", "ihost3")
        resp = await db_client.post(
            "/games/99999/invite",
            json={"invitee_email": "x@example.com"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


# ---- join flow --------------------------------------------------------------

class TestJoinGame:
    async def test_join_success(self, db_client: AsyncClient):
        host_token = await register_and_login(db_client, "jhost@example.com", "jhost")
        player_token = await register_and_login(db_client, "jplayer@example.com", "jplayer")
        game = await create_game(db_client, host_token)

        invite_resp = await db_client.post(
            f"/games/{game['id']}/invite",
            json={"invitee_email": "jplayer@example.com"},
            headers=auth_headers(host_token),
        )
        token = invite_resp.json()["token"]

        join_resp = await db_client.post(
            f"/games/{game['id']}/join",
            json={"token": token},
            headers=auth_headers(player_token),
        )
        assert join_resp.status_code == 201

        # Verify player appears in game
        game_resp = await db_client.get(f"/games/{game['id']}", headers=auth_headers(host_token))
        assert len(game_resp.json()["players"]) == 2

    async def test_join_invalid_token(self, db_client: AsyncClient):
        host_token = await register_and_login(db_client, "jh2@example.com", "jhost2")
        player_token = await register_and_login(db_client, "jp2@example.com", "jplayer2")
        game = await create_game(db_client, host_token)

        resp = await db_client.post(
            f"/games/{game['id']}/join",
            json={"token": "badtoken123"},
            headers=auth_headers(player_token),
        )
        assert resp.status_code == 400

    async def test_join_twice_fails(self, db_client: AsyncClient):
        host_token = await register_and_login(db_client, "jh3@example.com", "jhost3")
        player_token = await register_and_login(db_client, "jp3@example.com", "jplayer3")
        game = await create_game(db_client, host_token)

        invite_resp = await db_client.post(
            f"/games/{game['id']}/invite",
            json={"invitee_email": "jp3@example.com"},
            headers=auth_headers(host_token),
        )
        token = invite_resp.json()["token"]
        await db_client.post(
            f"/games/{game['id']}/join",
            json={"token": token},
            headers=auth_headers(player_token),
        )
        # Second attempt with same token should fail (already accepted)
        resp = await db_client.post(
            f"/games/{game['id']}/join",
            json={"token": token},
            headers=auth_headers(player_token),
        )
        assert resp.status_code == 400


# ---- species selection ------------------------------------------------------

class TestSelectSpecies:
    async def test_select_species_success(self, db_client: AsyncClient):
        token = await register_and_login(db_client, "sp@example.com", "spuser")
        game = await create_game(db_client, token)
        resp = await db_client.post(
            f"/games/{game['id']}/select-species",
            json={"species": "human"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["species"] == "human"

    async def test_select_species_duplicate_rejected(self, db_client: AsyncClient):
        host_token = await register_and_login(db_client, "sp2h@example.com", "sp2host")
        player_token = await register_and_login(db_client, "sp2p@example.com", "sp2player")
        game = await create_game(db_client, host_token)

        invite_resp = await db_client.post(
            f"/games/{game['id']}/invite",
            json={"invitee_email": "sp2p@example.com"},
            headers=auth_headers(host_token),
        )
        token_val = invite_resp.json()["token"]
        await db_client.post(
            f"/games/{game['id']}/join",
            json={"token": token_val},
            headers=auth_headers(player_token),
        )

        # Host picks human
        await db_client.post(
            f"/games/{game['id']}/select-species",
            json={"species": "human"},
            headers=auth_headers(host_token),
        )
        # Player tries to also pick human - should fail
        resp = await db_client.post(
            f"/games/{game['id']}/select-species",
            json={"species": "human"},
            headers=auth_headers(player_token),
        )
        assert resp.status_code == 400
        assert "taken" in resp.json()["detail"]

    async def test_select_species_not_in_game(self, db_client: AsyncClient):
        host_token = await register_and_login(db_client, "sp3h@example.com", "sp3host")
        other_token = await register_and_login(db_client, "sp3o@example.com", "sp3other")
        game = await create_game(db_client, host_token)
        resp = await db_client.post(
            f"/games/{game['id']}/select-species",
            json={"species": "planta"},
            headers=auth_headers(other_token),
        )
        assert resp.status_code == 400


# ---- start game -------------------------------------------------------------

class TestStartGame:
    async def test_start_game_success(self, db_client: AsyncClient):
        host_token = await register_and_login(db_client, "st@example.com", "sthost")
        p2_token = await register_and_login(db_client, "st2@example.com", "stplayer")
        game = await create_game(db_client, host_token, max_players=2)

        invite_resp = await db_client.post(
            f"/games/{game['id']}/invite",
            json={"invitee_email": "st2@example.com"},
            headers=auth_headers(host_token),
        )
        token_val = invite_resp.json()["token"]
        await db_client.post(
            f"/games/{game['id']}/join",
            json={"token": token_val},
            headers=auth_headers(p2_token),
        )
        await db_client.post(
            f"/games/{game['id']}/select-species",
            json={"species": "human"},
            headers=auth_headers(host_token),
        )
        await db_client.post(
            f"/games/{game['id']}/select-species",
            json={"species": "planta"},
            headers=auth_headers(p2_token),
        )

        resp = await db_client.post(f"/games/{game['id']}/start", headers=auth_headers(host_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["current_round"] == 1

    async def test_start_game_non_host_rejected(self, db_client: AsyncClient):
        host_token = await register_and_login(db_client, "st3h@example.com", "st3host")
        p2_token = await register_and_login(db_client, "st3p@example.com", "st3player")
        game = await create_game(db_client, host_token)

        invite_resp = await db_client.post(
            f"/games/{game['id']}/invite",
            json={"invitee_email": "st3p@example.com"},
            headers=auth_headers(host_token),
        )
        await db_client.post(
            f"/games/{game['id']}/join",
            json={"token": invite_resp.json()["token"]},
            headers=auth_headers(p2_token),
        )

        resp = await db_client.post(f"/games/{game['id']}/start", headers=auth_headers(p2_token))
        assert resp.status_code == 400
        assert "host" in resp.json()["detail"].lower()

    async def test_start_game_not_enough_players(self, db_client: AsyncClient):
        token = await register_and_login(db_client, "st4@example.com", "st4host")
        game = await create_game(db_client, token)
        await db_client.post(
            f"/games/{game['id']}/select-species",
            json={"species": "human"},
            headers=auth_headers(token),
        )
        resp = await db_client.post(f"/games/{game['id']}/start", headers=auth_headers(token))
        assert resp.status_code == 400
        assert "2 players" in resp.json()["detail"]

    async def test_start_game_missing_species(self, db_client: AsyncClient):
        host_token = await register_and_login(db_client, "st5h@example.com", "st5host")
        p2_token = await register_and_login(db_client, "st5p@example.com", "st5player")
        game = await create_game(db_client, host_token)

        invite_resp = await db_client.post(
            f"/games/{game['id']}/invite",
            json={"invitee_email": "st5p@example.com"},
            headers=auth_headers(host_token),
        )
        await db_client.post(
            f"/games/{game['id']}/join",
            json={"token": invite_resp.json()["token"]},
            headers=auth_headers(p2_token),
        )
        # Host selects species but player 2 does not
        await db_client.post(
            f"/games/{game['id']}/select-species",
            json={"species": "human"},
            headers=auth_headers(host_token),
        )

        resp = await db_client.post(f"/games/{game['id']}/start", headers=auth_headers(host_token))
        assert resp.status_code == 400
        assert "species" in resp.json()["detail"].lower()
