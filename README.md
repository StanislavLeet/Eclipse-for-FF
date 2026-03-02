# Eclipse: Second Dawn for the Galaxy

Browser-based digital implementation of the [Eclipse: Second Dawn for the Galaxy](https://lautapelit.fi/eclipse/) board game. Supports async turn-based multiplayer with email notifications.

**Stack:** Python 3.11 · FastAPI · SQLAlchemy 2.0 async · PostgreSQL · Alembic · Vanilla JS + SVG frontend

---

## Локальная инструкция на русском

Подробная пошаговая инструкция для локального запуска и проверки функциональности: [`docs/local-testing-setup-ru.md`](docs/local-testing-setup-ru.md).

---

## Prerequisites

- Python 3.11+
- PostgreSQL (local install or Docker)
- (Optional) `make` for convenience shortcuts

---

## Local Setup

### 1. Clone and create virtualenv

```bash
git clone <repo-url>
cd "Eclipse second dawn project"
python3.11 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
# Runtime + dev dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Or via make
make dev-install
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env — set DATABASE_URL and SECRET_KEY at minimum
```

Key variables in `.env`:

| Variable | Example | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@localhost/eclipse_game` | Production DB |
| `SECRET_KEY` | `change-me-32-chars-min` | JWT signing key |
| `SMTP_HOST` | `smtp.example.com` | Email notifications (optional) |
| `SMTP_PORT` | `587` | |
| `SMTP_USER` | `noreply@example.com` | |
| `SMTP_PASSWORD` | `...` | |

### 4. Create database and run migrations

```bash
# Create the database (PostgreSQL must be running)
make dev-db          # runs: createdb eclipse_game

# Apply all Alembic migrations
make migrate         # runs: alembic upgrade head
```

### 5. Start the development server

```bash
make run
# or directly:
venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now at `http://localhost:8000` and the interactive docs at `http://localhost:8000/docs`.

---

## Development Commands

| Command | What it does |
|---|---|
| `make run` | Start uvicorn dev server with auto-reload |
| `make test` | Run full test suite (pytest) |
| `make test-cov` | Run tests with coverage report |
| `make lint` | Run ruff linter |
| `make lint-fix` | Run ruff linter and auto-fix issues |
| `make migrate` | Apply pending Alembic migrations |
| `make migrate-down` | Roll back the last migration |
| `make install` | Install runtime dependencies only |
| `make dev-install` | Install runtime + dev dependencies |
| `make dev-db` | Create the `eclipse_game` PostgreSQL database |

### Run tests directly

```bash
# All tests
venv/bin/pytest

# With coverage
venv/bin/pytest --cov=app --cov-report=term-missing

# Single file
venv/bin/pytest tests/test_games.py -v
```

### Lint

```bash
venv/bin/ruff check .
venv/bin/ruff check . --fix   # auto-fix
```

### Migrations

```bash
# Apply
venv/bin/alembic upgrade head

# Rollback one
venv/bin/alembic downgrade -1

# Create new migration
venv/bin/alembic revision --autogenerate -m "describe change"
```

---

## Project Structure

```
.
├── app/
│   ├── main.py              # FastAPI app + router registration
│   ├── config.py            # Settings (pydantic-settings)
│   ├── database.py          # Async engine + get_db() dependency
│   ├── dependencies.py      # get_current_user() dependency
│   ├── models/              # SQLAlchemy ORM models
│   ├── routers/             # FastAPI routers (auth, games, turns, …)
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/            # Business logic layer
│   └── data/                # Static game data (species, technologies, …)
├── alembic/                 # Database migration scripts
├── frontend/                # Vanilla JS + SVG board frontend
├── tests/                   # pytest test suite
├── docs/                    # Plans and reference docs
├── Makefile
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

---

## API Overview

| Router | Base path | Purpose |
|---|---|---|
| auth | `/auth` | Register, login, JWT, logout |
| games | `/games` | Create/join games, lobby, invites, deletion |
| turns | `/turns` | Submit actions, advance phases |
| research | `/research` | Research technologies |
| ships | `/ships` | Build ships, upgrade blueprints |
| combat | `/combat` | Resolve combat, view logs |
| council | `/council` | Galactic Council votes and resolutions |

Interactive API docs: `GET /docs` (Swagger UI) or `GET /redoc`.

### Game Lifecycle Endpoints

#### Inviting and Joining

| Endpoint | Auth | Description |
|---|---|---|
| `POST /games/{id}/invite` | Player in game | Send an invite; body: `{"invitee_email": "<email>"}`. Returns a token. |
| `POST /games/{id}/join` | Any user | Join via token; body: `{"token": "<token>"}`. |

#### Species Selection

`POST /games/{id}/select-species` — body: `{"species": "<species_id>"}`.

- Pass any valid species ID to select that species. All species are exclusive except `"human"`, which multiple players may pick simultaneously.
- Pass `"random"` to have the server assign an available species at random (server-side, taking already-chosen species into account).

#### Game Deletion

| Endpoint | Auth | Description |
|---|---|---|
| `DELETE /games/{id}` | Host only | Delete a lobby game immediately, or initiate a player-approval workflow for an active game. |
| `POST /games/{id}/delete/approve` | Player in game | Approve a pending deletion request. Game is deleted once all players approve. |

Lobby games are deleted instantly by the host. Active games require the host to initiate deletion and every other player to approve via the approval endpoint.

All `GameResponse` objects include a `deletion_status` field (null when no deletion is in progress) with fields: `request_id`, `status`, `requested_by_user_id`, `pending_approvals`, `is_current_user_approved`, `can_current_user_approve`.

---

## Running Tests

Tests use SQLite (`sqlite+aiosqlite:///./test.db`) — no PostgreSQL required.

```bash
venv/bin/pytest                          # all 700+ tests
venv/bin/pytest --cov=app -q             # with coverage summary
venv/bin/pytest tests/test_combat.py -v  # single module
```

Coverage target: **80%+** (currently ~83%).

---

## Docker (Optional)

A `Dockerfile` and `docker-compose.yml` are not yet included. To run with Docker:

1. Build an image from the repo root using a standard Python 3.11 slim base.
2. Set `DATABASE_URL` to point at a PostgreSQL container.
3. Run `alembic upgrade head` as an entrypoint step before starting uvicorn.

---

## Game Rules Reference

See [`docs/game-rules-reference.md`](docs/game-rules-reference.md) for a developer-oriented summary of species abilities, technology effects, and VP scoring rules.
