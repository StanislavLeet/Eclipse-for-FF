# CLAUDE.md — Eclipse: Second Dawn Project

This file contains project-specific instructions for Claude Code. Follow these patterns for all code changes.

---

## Environment

- Python 3.11, virtualenv at `./venv`
- Run commands via `venv/bin/<tool>` (e.g. `venv/bin/pytest`, `venv/bin/ruff`)
- Never activate the venv; always use the full path

---

## Architecture

### Layers

```
routers/   →  schemas/  →  services/  →  models/
(HTTP)        (Pydantic)   (business)    (SQLAlchemy)
```

- **Routers** (`app/routers/`) — FastAPI `APIRouter`, HTTP only, no business logic
- **Services** (`app/services/`) — all game logic, called by routers and directly in tests
- **Models** (`app/models/`) — SQLAlchemy 2.0 declarative with `Mapped`/`mapped_column`
- **Schemas** (`app/schemas/`) — Pydantic v2 request/response models
- **Data** (`app/data/`) — static game data (species, technologies, tiles); pure Python, no DB

### Key files

| File | Purpose |
|---|---|
| `app/models/base.py` | `DeclarativeBase` — import Base from here |
| `app/models/__init__.py` | **Must import every model** so `Base.metadata.create_all` registers all tables |
| `app/database.py` | Async engine + `get_db()` dependency |
| `app/config.py` | `Settings` using `pydantic_settings.SettingsConfigDict` (NOT `class Config`) |
| `app/dependencies.py` | `get_current_user()` FastAPI dependency |
| `app/main.py` | App creation, CORS, router registration, static file mount |

---

## Database

- **Production**: `postgresql+asyncpg://...` (set in `.env`)
- **Tests**: `sqlite+aiosqlite:///./test.db`
- All DB operations are async (`await db.execute(...)`, `await db.commit()`, etc.)
- Use `await db.flush()` to get auto-generated IDs before committing

### Adding a new model

1. Create `app/models/<name>.py` with `class Foo(Base)`
2. Add `from app.models.<name> import Foo  # noqa: F401` to `app/models/__init__.py`
3. Generate migration: `venv/bin/alembic revision --autogenerate -m "add foo"`
4. Apply: `venv/bin/alembic upgrade head`

---

## Config

Use `pydantic-settings` with `SettingsConfigDict`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite+aiosqlite:///./test.db"
```

**Never** use the old-style `class Config` inner class.

---

## Testing

- Framework: `pytest-asyncio` with `asyncio_mode = "auto"` (in `pyproject.toml`)
- All test fixtures are **function-scoped** (not session-scoped)
- Test DB: SQLite via `aiosqlite`

### Fixture chain

```
db_engine  →  db_session  →  db_client
(creates schema)  (async session)  (FastAPI test client with DB override)
```

- `db_client` — `httpx.AsyncClient` with `ASGITransport`; use for integration tests
- `db_session` — `AsyncSession`; use for direct service-level tests (adds coverage)

### Coverage note

**Tests using `db_client` (HTTP) do NOT contribute to `pytest-cov` coverage** for router/service code because `httpx.ASGITransport` does not get traced by `coverage.py` in Python 3.11 + pytest-asyncio 1.3.0. Write direct `db_session` tests for any module where coverage is low.

### Running tests

```bash
venv/bin/pytest                           # full suite
venv/bin/pytest --cov=app -q              # with coverage
venv/bin/pytest tests/test_games.py -v   # single module
```

Coverage target: **80%+**.

---

## Linting

```bash
venv/bin/ruff check .        # check
venv/bin/ruff check . --fix  # auto-fix
```

All new code must pass ruff before committing. Never use `# noqa` to suppress errors in production code (only in `__init__.py` for re-export imports).

---

## Migrations

```bash
venv/bin/alembic upgrade head                              # apply all
venv/bin/alembic downgrade -1                             # roll back one
venv/bin/alembic revision --autogenerate -m "description" # generate
```

Migration files live in `alembic/versions/`. The `env.py` uses `asyncio.run` to handle async engines.

---

## Commit conventions

- Prefix: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`
- Example: `feat: Task 5 - resource income, colonization, upkeep engine`
- One logical change per commit; always include tests

---

## Common pitfalls

1. **Missing model import in `__init__.py`** — causes "no such table" in tests even though the model file exists. Always add new models to `app/models/__init__.py`.
2. **`class Config` in Settings** — use `SettingsConfigDict` instead or pydantic will warn/error.
3. **`asyncio_mode = "auto"`** — do NOT add `@pytest.mark.asyncio` to individual tests; the global setting covers all async tests.
4. **Function-scoped fixtures** — using session-scoped fixtures with `asyncio_mode = "auto"` causes event loop conflicts. Keep all fixtures function-scoped.
5. **Game deletion is status-dependent** — `DELETE /games/{id}` for a **lobby** game calls `delete_game_directly()` and returns immediately. For an **active** game it calls `request_or_approve_game_deletion()` to start an approval workflow. Never route lobby deletions through the approval workflow; doing so creates a `GameDeletionRequest` record instead of deleting the game.
6. **Species `"random"` is resolved server-side** — `POST /games/{id}/select-species` accepts the literal string `"random"` and picks a free species on the server. Do not resolve `"random"` to a concrete species on the client; the server is the only place with a consistent view of taken species.
