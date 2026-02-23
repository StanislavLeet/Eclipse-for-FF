---
# Eclipse: Second Dawn for the Galaxy - Full Project Implementation Plan

## Overview
A browser-based, full-rule-enforcement digital implementation of the Eclipse: Second Dawn for the Galaxy board game.
Built with Python FastAPI + PostgreSQL backend and a JavaScript browser frontend. Supports turn-based async multiplayer
with email notifications. Private use among friends and family.

## Context
- Files involved: None yet (greenfield project)
- Related patterns: None (starting from scratch)
- Dependencies: Python 3.11+, FastAPI, SQLAlchemy, PostgreSQL, Alembic (migrations), Jinja2, smtplib or SendGrid for email, pytest, JavaScript (canvas or SVG for board rendering)

## Development Approach
- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- Backend: FastAPI REST API serving JSON to a browser frontend
- Frontend: Vanilla JavaScript + SVG/Canvas for the hex board, HTML/CSS for UI panels
- Database: PostgreSQL via SQLAlchemy ORM with Alembic migrations
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

---

## Implementation Steps

### Task 1: Project Setup & Infrastructure

**Files:**
- Create: `pyproject.toml` or `requirements.txt`
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `app/config.py`
- Create: `app/database.py`
- Create: `alembic.ini` and `alembic/env.py`
- Create: `frontend/index.html`, `frontend/style.css`, `frontend/main.js`
- Create: `tests/__init__.py`, `tests/conftest.py`
- Create: `Makefile` (dev shortcuts)
- Create: `.env.example`

- [x] Initialize Python project with FastAPI, SQLAlchemy, Alembic, pytest, python-dotenv dependencies
- [x] Configure FastAPI app with CORS, static file serving for frontend
- [x] Set up PostgreSQL connection via SQLAlchemy async engine
- [x] Set up Alembic for database migrations
- [x] Create basic health check endpoint `GET /health`
- [x] Create frontend scaffold (index.html, empty JS/CSS)
- [x] Write conftest.py with test database setup using a separate test DB
- [x] Write smoke test: health check returns 200
- [x] Run test suite - must pass before task 2

### Task 2: Database Models - Users, Games, Players

**Files:**
- Create: `app/models/user.py`
- Create: `app/models/game.py`
- Create: `app/models/player.py`
- Create: `app/models/base.py`
- Create: `alembic/versions/001_initial_schema.py`

- [x] Define `User` model: id, email, username, hashed_password, created_at
- [x] Define `Game` model: id, name, status (lobby/active/finished), current_round, current_phase, max_players, created_at
- [x] Define `Player` model: id, game_id, user_id, species, turn_order, is_active_turn, vp_count
- [x] Define `GameInvite` model: id, game_id, invitee_email, token, accepted
- [x] Run Alembic migration to create tables
- [x] Write model unit tests (create, read, relationships)
- [x] Run test suite - must pass before task 3

### Task 3: User Authentication

**Files:**
- Create: `app/routers/auth.py`
- Create: `app/schemas/auth.py`
- Create: `app/services/auth_service.py`
- Create: `app/dependencies.py` (get_current_user)
- Modify: `app/main.py`

- [x] Implement `POST /auth/register` (email, username, password)
- [x] Implement `POST /auth/login` returning JWT access token
- [x] Implement `GET /auth/me` returning current user info
- [x] Implement `POST /auth/logout` (invalidate token)
- [x] Add `get_current_user` dependency for protected routes
- [x] Hash passwords with bcrypt
- [x] Write auth tests: register, login, protected route access, invalid credentials
- [x] Run test suite - must pass before task 4

### Task 4: Game Lobby & Species Selection

**Files:**
- Create: `app/routers/games.py`
- Create: `app/schemas/game.py`
- Create: `app/services/game_service.py`
- Create: `app/data/species.py` (static species definitions)
- Modify: `alembic/versions/` (new migration if needed)

- [x] Define all 9 species as static data: Human, Eridani Empire, Hydran Progress, Planta, Descendants of Draco, Mechanema, Orion Hegemony, Exiles, Terran Directorate -- each with starting resources, homeworld stats, special abilities
- [x] Implement `POST /games` (create game, set max players 2-6, map size)
- [x] Implement `GET /games/{id}` (game info, player list)
- [x] Implement `POST /games/{id}/invite` (send invite email with token link)
- [x] Implement `POST /games/{id}/join` (accept invite, join lobby)
- [x] Implement `POST /games/{id}/select-species` (choose species, validate no duplicates)
- [x] Implement `POST /games/{id}/start` (host starts game, validates all players ready, triggers map generation)
- [x] Write tests: game creation, invite flow, species selection uniqueness, start validation
- [x] Run test suite - must pass before task 5

### Task 5: Galaxy Map Generation

**Files:**
- Create: `app/models/hex_tile.py`
- Create: `app/models/system.py`
- Create: `app/data/system_tiles.py` (all tile definitions)
- Create: `app/services/map_generator.py`
- Create: `alembic/versions/003_map_schema.py`

- [x] Define `HexTile` model: id, game_id, q, r (axial coords), tile_type, is_explored, owner_player_id
- [x] Define `System` model: id, hex_tile_id, name, planets (JSON), wormholes (JSON), ancient_ships_count, discovery_tile_id
- [x] Encode all real Eclipse system tiles as static data (tile ID, planets with hex types, wormholes, starting resources)
- [x] Implement hex grid layout algorithm (axial coordinate system, ring-based layout for 2-6 players)
- [x] Implement map generator: place Galactic Center (tile 001), distribute system tiles by ring, place homeworld tiles for each player at correct positions
- [x] Implement wormhole connection validation (wormhole exits must align between adjacent tiles)
- [x] Write tests: map generation for 2/3/4/5/6 players, wormhole alignment, homeworld placement
- [x] Run test suite - must pass before task 6

### Task 6: Core Game State & Turn Engine

**Files:**
- Create: `app/models/game_action.py`
- Create: `app/services/turn_engine.py`
- Create: `app/routers/turns.py`
- Create: `app/schemas/turn.py`

- [x] Define game phases enum: STRATEGY, ACTIVATION (with sub-phases), COMBAT, UPKEEP
- [x] Define player actions enum: EXPLORE, INFLUENCE, BUILD, RESEARCH, MOVE, UPGRADE, PASS
- [x] Define `GameAction` model: id, game_id, player_id, action_type, payload (JSON), timestamp, round_number
- [x] Implement turn order enforcement: track who has passed, who is active
- [x] Implement `POST /games/{id}/action` (player submits action, validates it is their turn, validates action is legal given game state)
- [x] Implement phase transition logic: when all players pass in Activation, move to Combat; after Combat, Upkeep; after Upkeep, new round
- [x] Implement action history `GET /games/{id}/actions`
- [x] Write tests: turn order, illegal action rejection, phase transitions
- [x] Run test suite - must pass before task 7

### Task 7: Resource Management

**Files:**
- Create: `app/models/player_resources.py`
- Create: `app/services/resource_service.py`
- Modify: `app/services/turn_engine.py`

- [x] Define `PlayerResources` model: player_id, money, science, materials, population_cubes (by type: orbital, advanced, Gauss), tradespheres
- [x] Implement starting resource allocation per species on game start
- [x] Implement influence track (11 influence discs per player, placed on action tiles and colony hexes)
- [x] Implement upkeep calculation: sum colony income + trade + modifiers, deduct influence costs, handle bankruptcy (discard colony if can't pay)
- [x] Implement spending validation on actions (e.g. BUILD costs materials, RESEARCH costs science)
- [x] Implement `GET /games/{id}/players/{id}/resources`
- [x] Write tests: upkeep calculation, bankruptcy, species-specific starting resources, spending validation
- [x] Run test suite - must pass before task 8

### Task 8: Technology Research Tree

**Files:**
- Create: `app/data/technologies.py` (all tech definitions)
- Create: `app/models/player_technology.py`
- Create: `app/services/research_service.py`
- Create: `app/routers/research.py`

- [x] Define all Eclipse technologies as static data (6 categories: Military, Grid, Nano, Quantum, Rare-element, Ancient): name, category, cost, prerequisites, effects
- [x] Define `PlayerTechnology` model: player_id, tech_id, acquired_round
- [x] Implement RESEARCH action validation: player has enough science, prerequisites met, tech not already owned
- [x] Implement research cost reduction (each owned tech in same category reduces cost by 1)
- [x] Apply tech effects to player state (e.g. Advanced Mining +1 material per advanced square)
- [x] Implement `GET /games/{id}/players/{id}/technologies`
- [x] Implement `POST /games/{id}/action` RESEARCH sub-handler
- [x] Write tests: prerequisite enforcement, cost calculation with reductions, effect application
- [x] Run test suite - must pass before task 9

### Task 9: Ship System & Blueprints

**Files:**
- Create: `app/data/ship_parts.py` (all component definitions)
- Create: `app/models/ship.py`
- Create: `app/models/ship_blueprint.py`
- Create: `app/services/ship_service.py`
- Create: `app/routers/ships.py`

- [x] Define all ship components as static data: Cannons, Missiles, Shields, Drives, Hull, Computer, Source -- with stats (initiative, power consumption, power output, damage, hits)
- [x] Define 4 ship types: Interceptor, Cruiser, Dreadnought, Starbase -- with slot counts and base stats
- [x] Define `ShipBlueprint` model: player_id, ship_type, component slots (JSON), is_valid (sufficient power)
- [x] Define `Ship` model: id, game_id, player_id, ship_type, hex_tile_id, hp_remaining, is_ancient
- [x] Implement UPGRADE action: modify blueprint, validate power balance, validate components unlocked via tech
- [x] Implement BUILD action: spend materials per ship type, place ship on player homeworld hex
- [x] Implement blueprint validation (power must not be negative, required slots filled)
- [x] Initialize default blueprints per species on game start
- [x] Write tests: blueprint validation, power balance, build cost, species-specific defaults
- [x] Run test suite - must pass before task 10

### Task 10: Movement & Exploration

**Files:**
- Create: `app/services/movement_service.py`
- Create: `app/services/exploration_service.py`
- Create: `app/models/discovery_tile.py`
- Modify: `app/routers/turns.py`

- [x] Define discovery tiles as static data (positive: resources/tech/ships, negative: nothing)
- [x] Implement MOVE action: validate path through connected hexes (wormholes or adjacent), validate drive count vs hexes moved, move ship models in DB
- [x] Implement hex ownership (INFLUENCE action: place influence disc on explored system)
- [x] Implement EXPLORE action: reveal unexplored tile when ship enters, draw discovery tile, apply discovery effect, validate player can afford to keep influence disc or must retreat
- [x] Handle ancient ship encounters during exploration (place ancient ships if tile has them)
- [x] Implement `GET /games/{id}/map` returning all hex tiles with their state
- [x] Write tests: movement path validation, exploration reveal, discovery tile draw, ancient ship placement
- [x] Run test suite - must pass before task 11

### Task 11: Colonization & Population Management

**Files:**
- Create: `app/models/planet_population.py`
- Create: `app/services/colony_service.py`
- Modify: `app/routers/turns.py`

- [x] Define `PlanetPopulation` model: id, hex_tile_id, planet_slot, population_type (orbital/advanced/Gauss), owner_player_id
- [x] Implement colony ship build + movement (colony ships are consumed on colonization)
- [x] Implement colonization action: place population cube on planet slot, validate cube type matches planet type (Money/Science/Materials)
- [x] Implement population growth (INFLUENCE action can also upgrade population track)
- [x] Enforce max population per hex based on planet slots
- [x] Calculate colony income contribution during upkeep
- [x] Handle population removal during combat (attacker may place their population)
- [x] Write tests: colonization validation, income calculation, population limits
- [x] Run test suite - must pass before task 12

### Task 12: Combat System

**Files:**
- Create: `app/services/combat_service.py`
- Create: `app/models/combat_log.py`
- Create: `app/routers/combat.py`

- [x] Define combat sequence: 1) Missiles (if any), 2) Cannons by initiative order, 3) Apply damage, 4) Remove destroyed ships
- [x] Implement initiative calculation per ship (base initiative + Computer bonus)
- [x] Implement dice rolling: each cannon/missile rolls 1d6 + Computer vs target's Shield value
- [x] Implement hit application: reduce ship HP, destroy at 0 (dreadnoughts have 2 HP by default)
- [x] Implement retreat option (before combat round, must move to adjacent hex)
- [x] Implement combat VP: 1VP per enemy ship destroyed (player ships) or 2VP (ancient/GCDS)
- [x] Define `CombatLog` model: id, game_id, hex_tile_id, round_number, attacker_id, log_entries (JSON)
- [x] Handle GCDS (Galactic Center Defense System) as special ancient ship
- [x] Write tests: initiative ordering, hit calculation, damage application, retreat validation, VP award
- [x] Run test suite - must pass before task 13

### Task 13: Galactic Council & Politics

**Files:**
- Create: `app/models/council.py`
- Create: `app/data/resolutions.py`
- Create: `app/services/council_service.py`
- Create: `app/routers/council.py`

- [ ] Define Resolution cards as static data (all Eclipse resolutions: tax, military, trade, etc. with their effects)
- [ ] Define `CouncilState` model: game_id, current_resolution_id, ambassador_placements (JSON per player), vp_from_council (JSON per player)
- [ ] Implement ambassador placement (players place ambassadors from their supply based on controlled systems)
- [ ] Implement voting: count ambassadors per resolution side, determine winner
- [ ] Apply resolution effects to game state (modify resource income, VP, etc.)
- [ ] Implement council VP: 1VP per ambassador on winning side
- [ ] Trigger Galactic Council vote during Upkeep phase once Galactic Center is explored
- [ ] Write tests: ambassador count, voting tallying, resolution effect application, VP distribution
- [ ] Run test suite - must pass before task 14

### Task 14: Email Notifications & Async Turn Handoff

**Files:**
- Create: `app/services/notification_service.py`
- Create: `app/tasks/email_sender.py`
- Modify: `app/services/turn_engine.py`

- [ ] Configure email sending (SMTP or SendGrid via config)
- [ ] Send notification email when it becomes a player's turn: include game name, round, what phase, link to game
- [ ] Send notification email when game starts (invite accepted + game launched)
- [ ] Send notification email when game ends (winner announced)
- [ ] Implement email queue/retry (simple: direct send with error logging, no external queue needed for personal use scale)
- [ ] Implement `GET /games/{id}/status` for players to check game state without email
- [ ] Write tests: notification is triggered on turn change, email content contains game link
- [ ] Run test suite - must pass before task 15

### Task 15: Victory Points & End Game

**Files:**
- Create: `app/services/victory_service.py`
- Modify: `app/services/turn_engine.py`
- Modify: `app/routers/games.py`

- [ ] Define all VP sources: colony control (1VP per controlled system), tech VP (listed on tech cards), ships destroyed in combat, council votes, discovery tiles, reputation tiles, sector control (VP based on systems at game end)
- [ ] Implement VP tracking model (already on Player, but add VP breakdown JSON for display)
- [ ] Implement end-game trigger: after round 8 (standard game end) or if all rounds exhausted
- [ ] Implement final VP tally: sum all VP sources for each player
- [ ] Implement tiebreaker (most money wins tie)
- [ ] Implement `GET /games/{id}/scores` returning current VP standings
- [ ] Mark game status as "finished", send end-game notification emails
- [ ] Write tests: VP calculation, tiebreaker, end-game trigger at round 8
- [ ] Run test suite - must pass before task 16

### Task 16: Frontend - Board Rendering

**Files:**
- Create: `frontend/board.js`
- Create: `frontend/hex_renderer.js`
- Create: `frontend/api.js`
- Modify: `frontend/index.html`
- Modify: `frontend/style.css`

- [ ] Implement hex grid rendering using SVG (axial coordinate to pixel conversion for flat-top hexagons)
- [ ] Render each tile: unexplored (face-down), explored (show planet slots, wormhole indicators, owner color)
- [ ] Render ships on hexes (colored icons per player per ship type)
- [ ] Render population cubes on planet slots (colored per owner)
- [ ] Implement pan and zoom on the board (mouse wheel + drag)
- [ ] Fetch and render `GET /games/{id}/map` on page load and after each action
- [ ] Highlight valid action targets when player selects an action (e.g. highlight reachable hexes for MOVE)
- [ ] Write frontend tests (basic: API fetch mocking, hex coordinate math)
- [ ] Run test suite - must pass before task 17

### Task 17: Frontend - Player Actions UI

**Files:**
- Create: `frontend/actions.js`
- Create: `frontend/panels.js`
- Modify: `frontend/index.html`
- Modify: `frontend/style.css`

- [ ] Implement sidebar panels: player resources, owned technologies, ship blueprints, turn order indicator
- [ ] Implement action selection UI (action tiles panel: EXPLORE, INFLUENCE, BUILD, RESEARCH, MOVE, UPGRADE, PASS)
- [ ] Implement action confirmation dialogs (e.g. confirm ship to build, confirm tech to research)
- [ ] Implement turn notification UI: banner showing whose turn it is
- [ ] Implement combat log display (show combat results when combat phase occurs)
- [ ] Implement VP scoreboard panel (visible to all players)
- [ ] Implement responsive layout for common screen sizes (1280px+)
- [ ] Implement login/register pages and game lobby UI (create game, invite players, species picker)
- [ ] Write frontend tests: UI state transitions, form validation
- [ ] Run test suite - must pass before task 18

### Task 18: Verify Acceptance Criteria

- [ ] Manual test: two players create a game, invite each other, select species, start game
- [ ] Manual test: complete a full game turn cycle (all phases) with at least one combat
- [ ] Manual test: research a technology and verify effects apply correctly
- [ ] Manual test: play through 8 rounds and verify game ends with correct winner
- [ ] Manual test: email notification received when turn changes
- [ ] Manual test: illegal move (e.g. moving ship through unconnected hex) is rejected with clear error
- [ ] Run full backend test suite: `pytest` -- must pass 100%
- [ ] Run linter: `ruff check .` or `flake8` -- must pass
- [ ] Verify test coverage: `pytest --cov=app` -- 80%+ coverage

### Task 19: Update Documentation

- [ ] Update README.md with setup instructions, local dev commands, how to run with Docker (optional)
- [ ] Document species abilities and technology effects in a `docs/game-rules-reference.md` for developer reference
- [ ] Update CLAUDE.md if internal patterns changed
- [ ] Move this plan to `docs/plans/completed/`
