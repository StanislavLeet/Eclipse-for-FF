from httpx import AsyncClient


async def register_user(client: AsyncClient, email="alice@example.com", username="alice", password="secret123"):
    return await client.post("/auth/register", json={"email": email, "username": username, "password": password})


async def login_user(client: AsyncClient, email="alice@example.com", password="secret123"):
    return await client.post("/auth/login", json={"email": email, "password": password})


class TestRegister:
    async def test_register_success(self, db_client: AsyncClient):
        resp = await register_user(db_client)
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "alice@example.com"
        assert data["username"] == "alice"
        assert "id" in data
        assert "hashed_password" not in data

    async def test_register_duplicate_email(self, db_client: AsyncClient):
        await register_user(db_client)
        resp = await register_user(db_client)
        assert resp.status_code == 409
        assert "Email" in resp.json()["detail"]

    async def test_register_duplicate_username(self, db_client: AsyncClient):
        await register_user(db_client, email="alice@example.com", username="alice")
        resp = await register_user(db_client, email="other@example.com", username="alice")
        assert resp.status_code == 409
        assert "Username" in resp.json()["detail"]

    async def test_register_invalid_email(self, db_client: AsyncClient):
        resp = await db_client.post(
            "/auth/register", json={"email": "not-an-email", "username": "bob", "password": "pass"}
        )
        assert resp.status_code == 422


class TestLogin:
    async def test_login_success(self, db_client: AsyncClient):
        await register_user(db_client)
        resp = await login_user(db_client)
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, db_client: AsyncClient):
        await register_user(db_client)
        resp = await login_user(db_client, password="wrongpassword")
        assert resp.status_code == 401

    async def test_login_unknown_email(self, db_client: AsyncClient):
        resp = await login_user(db_client, email="nobody@example.com")
        assert resp.status_code == 401


class TestMe:
    async def test_me_success(self, db_client: AsyncClient):
        await register_user(db_client)
        login_resp = await login_user(db_client)
        token = login_resp.json()["access_token"]

        resp = await db_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "alice@example.com"
        assert data["username"] == "alice"

    async def test_me_no_token(self, db_client: AsyncClient):
        resp = await db_client.get("/auth/me")
        assert resp.status_code == 401

    async def test_me_invalid_token(self, db_client: AsyncClient):
        resp = await db_client.get("/auth/me", headers={"Authorization": "Bearer invalidtoken"})
        assert resp.status_code == 401


class TestLogout:
    async def test_logout_success(self, db_client: AsyncClient):
        await register_user(db_client)
        login_resp = await login_user(db_client)
        token = login_resp.json()["access_token"]

        resp = await db_client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 204

    async def test_logout_no_token(self, db_client: AsyncClient):
        resp = await db_client.post("/auth/logout")
        assert resp.status_code == 401
