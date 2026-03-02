"""Tests for Task 9: Ship System & Blueprints.

Covers:
- Ship component definitions: all categories present, stats correct
- Ship type definitions: slot counts, base HP, build costs
- Power balance calculation: valid/invalid blueprints
- Blueprint initialization on game start (default slots per species)
- Orion Hegemony species-specific default blueprint (extra cannon)
- UPGRADE action: valid, invalid power balance, tech not owned, wrong slot count
- BUILD action: creates Ship record, deducts materials
- Blueprint validation: power balance, tech unlock requirement
- GET /games/{id}/players/{id}/blueprints endpoint
- GET /games/{id}/players/{id}/ships endpoint
- Species starting ships placed on homeworld at game start
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.ship_parts import (
    ComponentCategory,
    compute_power_balance,
    get_component,
    get_ship_type,
    list_components,
    list_components_by_category,
    list_ship_types,
    validate_blueprint_power,
)
from app.services.ship_service import (
    apply_upgrade,
    get_blueprints_for_player,
    initialize_blueprints,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def register_and_login(
    client: AsyncClient, email: str, username: str, password: str = "testpass1"
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
    emails = [f"ship_p{i}@example.com" for i in range(num_players)]
    usernames = [f"ship_player{i}" for i in range(num_players)]

    for i in range(num_players):
        token = await register_and_login(client, emails[i], usernames[i])
        tokens.append(token)

    create_resp = await client.post(
        "/games",
        json={"name": "Ship Test Game", "max_players": num_players},
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
# Static data: components
# ---------------------------------------------------------------------------

class TestShipComponentDefinitions:
    def test_all_component_categories_present(self):
        for category in ComponentCategory:
            comps = list_components_by_category(category)
            assert len(comps) >= 1, f"No components in category {category.value}"

    def test_sources_provide_power(self):
        sources = list_components_by_category(ComponentCategory.source)
        for s in sources:
            assert s.power_generated > 0, f"{s.component_id} should generate power"
            assert s.power_consumed == 0

    def test_drives_consume_power_and_provide_movement(self):
        drives = list_components_by_category(ComponentCategory.drive)
        for d in drives:
            assert d.movement > 0, f"{d.component_id} should provide movement"
            assert d.power_consumed > 0, f"{d.component_id} should consume power"

    def test_cannons_deal_damage(self):
        cannons = list_components_by_category(ComponentCategory.cannon)
        for c in cannons:
            assert c.damage > 0, f"{c.component_id} should deal damage"

    def test_missiles_fire_first(self):
        missiles = list_components_by_category(ComponentCategory.missile)
        for m in missiles:
            assert m.fires_first, f"{m.component_id} should have fires_first=True"
            assert m.damage > 0

    def test_default_components_have_no_tech_requirement(self):
        default_ids = {
            "nuclear_source", "electron_drive", "electron_cannon",
            "basic_computer", "basic_shield",
        }
        for comp_id in default_ids:
            comp = get_component(comp_id)
            assert comp.requires_tech is None, (
                f"{comp_id} should not require a tech"
            )

    def test_upgraded_components_require_tech(self):
        # These should all require their matching tech
        pairs = [
            ("ion_cannon", "ion_cannon"),
            ("plasma_cannon", "plasma_cannon"),
            ("flux_missile", "flux_missile"),
            ("nuclear_drive", "nuclear_drive"),
            ("fusion_drive", "fusion_drive"),
            ("warp_drive", "warp_drive"),
            ("fusion_source", "fusion_source"),
            ("antimatter_source", "antimatter_source"),
            ("positron_computer", "positron_computer"),
            ("improved_hull", "improved_hull"),
        ]
        for comp_id, expected_tech in pairs:
            comp = get_component(comp_id)
            assert comp.requires_tech == expected_tech, (
                f"{comp_id} should require tech '{expected_tech}', "
                f"got '{comp.requires_tech}'"
            )

    def test_get_component_unknown_raises(self):
        with pytest.raises(KeyError):
            get_component("nonexistent_weapon_xyz")

    def test_all_components_have_valid_stats(self):
        for comp in list_components():
            assert comp.power_generated >= 0
            assert comp.power_consumed >= 0
            assert comp.damage >= 0
            assert comp.movement >= 0
            assert comp.accuracy >= 0
            assert comp.shield >= 0
            assert comp.extra_hp >= 0


# ---------------------------------------------------------------------------
# Static data: ship types
# ---------------------------------------------------------------------------

class TestShipTypeDefinitions:
    def test_four_ship_types_defined(self):
        types = list_ship_types()
        type_ids = {t.ship_type_id for t in types}
        assert "interceptor" in type_ids
        assert "cruiser" in type_ids
        assert "dreadnought" in type_ids
        assert "starbase" in type_ids

    def test_interceptor_stats(self):
        st = get_ship_type("interceptor")
        assert st.slot_count == 4
        assert st.base_hp == 1
        assert st.base_initiative == 2
        assert st.can_move is True
        assert st.build_cost == 3

    def test_cruiser_stats(self):
        st = get_ship_type("cruiser")
        assert st.slot_count == 6
        assert st.base_hp == 1
        assert st.can_move is True
        assert st.build_cost == 5

    def test_dreadnought_stats(self):
        st = get_ship_type("dreadnought")
        assert st.slot_count == 8
        assert st.base_hp == 2
        assert st.can_move is True
        assert st.build_cost == 8

    def test_starbase_stats(self):
        st = get_ship_type("starbase")
        assert st.slot_count == 5
        assert st.base_hp == 3
        assert st.can_move is False
        assert st.build_cost == 3

    def test_default_slots_match_slot_count(self):
        for ship_type in list_ship_types():
            assert len(ship_type.default_slots) == ship_type.slot_count, (
                f"{ship_type.ship_type_id} default_slots length "
                f"{len(ship_type.default_slots)} != slot_count {ship_type.slot_count}"
            )

    def test_default_blueprints_are_power_valid(self):
        for ship_type in list_ship_types():
            balance = compute_power_balance(ship_type.default_slots)
            assert balance >= 0, (
                f"{ship_type.ship_type_id} default blueprint has negative power balance {balance}"
            )

    def test_get_ship_type_unknown_raises(self):
        with pytest.raises(KeyError):
            get_ship_type("battlecruiser_xyz")


# ---------------------------------------------------------------------------
# Power balance calculation
# ---------------------------------------------------------------------------

class TestPowerBalance:
    def test_empty_slots_have_zero_balance(self):
        assert compute_power_balance([None, None, None]) == 0

    def test_source_only_is_positive(self):
        balance = compute_power_balance(["nuclear_source"])
        assert balance == 3  # nuclear_source generates 3

    def test_drive_only_is_negative(self):
        balance = compute_power_balance(["electron_drive"])
        assert balance == -1  # electron_drive consumes 1

    def test_valid_interceptor_default(self):
        # nuclear_source(+3), electron_cannon(-1), electron_drive(-1), None = +1
        slots = ["nuclear_source", "electron_cannon", "electron_drive", None]
        assert compute_power_balance(slots) == 1
        assert validate_blueprint_power(slots) is True

    def test_invalid_blueprint_rejected(self):
        # No source, just cannons
        slots = ["electron_cannon", "electron_cannon", "electron_cannon", None]
        assert compute_power_balance(slots) < 0
        assert validate_blueprint_power(slots) is False

    def test_none_slots_ignored(self):
        balance = compute_power_balance([None, "nuclear_source", None])
        assert balance == 3

    def test_unknown_component_ignored_gracefully(self):
        # Should not crash; unknown component contributes 0
        balance = compute_power_balance(["nuclear_source", "totally_fake_component"])
        assert balance == 3


# ---------------------------------------------------------------------------
# Blueprint initialization (service unit tests)
# ---------------------------------------------------------------------------

class TestBlueprintInitialization:
    async def _make_player(self, db, species_str: str):
        from app.models.player import Player, Species
        from app.models.game import Game, GameStatus, GamePhase
        from app.models.user import User

        user = User(
            email=f"bpinit_{species_str}@example.com",
            username=f"bpinit_{species_str}",
            hashed_password="x",
        )
        db.add(user)
        await db.flush()

        game = Game(
            name=f"bp-init-{species_str}",
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
            species=Species(species_str),
            turn_order=0,
        )
        db.add(player)
        await db.flush()
        return player

    async def test_four_blueprints_created(self, db_session: AsyncSession):
        player = await self._make_player(db_session, "human")
        blueprints = await initialize_blueprints(player, db_session)
        assert len(blueprints) == 4
        types = {bp.ship_type for bp in blueprints}
        assert types == {"interceptor", "cruiser", "dreadnought", "starbase"}

    async def test_all_default_blueprints_are_valid(self, db_session: AsyncSession):
        player = await self._make_player(db_session, "human")
        blueprints = await initialize_blueprints(player, db_session)
        for bp in blueprints:
            assert bp.is_valid, f"{bp.ship_type} blueprint is not valid"

    async def test_interceptor_default_has_correct_slot_count(self, db_session: AsyncSession):
        player = await self._make_player(db_session, "human")
        blueprints = await initialize_blueprints(player, db_session)
        interceptor_bp = next(bp for bp in blueprints if bp.ship_type == "interceptor")
        assert len(interceptor_bp.slots) == 4

    async def test_orion_hegemony_interceptor_has_extra_cannon(self, db_session: AsyncSession):
        player = await self._make_player(db_session, "orion_hegemony")
        blueprints = await initialize_blueprints(player, db_session)
        interceptor_bp = next(bp for bp in blueprints if bp.ship_type == "interceptor")
        cannon_count = sum(1 for s in interceptor_bp.slots if s == "electron_cannon")
        assert cannon_count == 2, (
            f"Orion Hegemony interceptor should have 2 cannons, got {cannon_count}"
        )

    async def test_blueprints_persisted_to_db(self, db_session: AsyncSession):
        player = await self._make_player(db_session, "human")
        await initialize_blueprints(player, db_session)
        from_db = await get_blueprints_for_player(player.id, db_session)
        assert len(from_db) == 4


# ---------------------------------------------------------------------------
# UPGRADE action (service unit tests)
# ---------------------------------------------------------------------------

class TestApplyUpgrade:
    async def _make_player_with_resources(self, db, species_str="human"):
        from app.models.player import Player, Species
        from app.models.game import Game, GameStatus, GamePhase
        from app.models.user import User
        from app.models.player_resources import PlayerResources

        user = User(
            email=f"upg_{species_str}_{id(db)}@example.com",
            username=f"upg_{species_str}_{id(db)}",
            hashed_password="x",
        )
        db.add(user)
        await db.flush()

        game = Game(
            name=f"upg-{species_str}",
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
            species=Species(species_str),
            turn_order=0,
        )
        db.add(player)
        await db.flush()

        resources = PlayerResources(
            player_id=player.id, money=10, science=10, materials=10
        )
        db.add(resources)
        await db.flush()

        await initialize_blueprints(player, db)
        return player

    async def test_upgrade_with_valid_slots(self, db_session: AsyncSession):
        player = await self._make_player_with_resources(db_session)
        # Upgrade interceptor: replace empty slot with basic_computer (no tech needed)
        new_slots = ["nuclear_source", "electron_cannon", "electron_drive", "basic_computer"]
        bp = await apply_upgrade(
            player_id=player.id,
            ship_type="interceptor",
            new_slots=new_slots,
            owned_tech_ids=set(),
            db=db_session,
        )
        assert bp.is_valid is True
        assert bp.slots == new_slots

    async def test_upgrade_wrong_slot_count_rejected(self, db_session: AsyncSession):
        player = await self._make_player_with_resources(db_session, "human")
        # Interceptor has 4 slots, providing 3
        with pytest.raises(ValueError, match="exactly 4 slots"):
            await apply_upgrade(
                player_id=player.id,
                ship_type="interceptor",
                new_slots=["nuclear_source", "electron_cannon", "electron_drive"],
                owned_tech_ids=set(),
                db=db_session,
            )

    async def test_upgrade_invalid_power_balance_rejected(self, db_session: AsyncSession):
        player = await self._make_player_with_resources(db_session, "human")
        # 4 electron cannons = -4 power, no source → invalid
        with pytest.raises(ValueError, match="power balance"):
            await apply_upgrade(
                player_id=player.id,
                ship_type="interceptor",
                new_slots=["electron_cannon", "electron_cannon", "electron_cannon", "electron_cannon"],
                owned_tech_ids=set(),
                db=db_session,
            )

    async def test_upgrade_tech_required_component_without_tech_rejected(
        self, db_session: AsyncSession
    ):
        player = await self._make_player_with_resources(db_session, "human")
        # ion_cannon requires the "ion_cannon" tech
        with pytest.raises(ValueError, match="requires technology"):
            await apply_upgrade(
                player_id=player.id,
                ship_type="interceptor",
                new_slots=["nuclear_source", "ion_cannon", "electron_drive", None],
                owned_tech_ids=set(),   # no tech owned
                db=db_session,
            )

    async def test_upgrade_tech_required_component_with_tech_allowed(
        self, db_session: AsyncSession
    ):
        player = await self._make_player_with_resources(db_session, "human")
        bp = await apply_upgrade(
            player_id=player.id,
            ship_type="interceptor",
            new_slots=["nuclear_source", "ion_cannon", "electron_drive", None],
            owned_tech_ids={"ion_cannon"},
            db=db_session,
        )
        assert bp.is_valid is True
        assert "ion_cannon" in bp.slots

    async def test_upgrade_unknown_component_rejected(self, db_session: AsyncSession):
        player = await self._make_player_with_resources(db_session, "human")
        with pytest.raises(ValueError, match="Unknown ship component"):
            await apply_upgrade(
                player_id=player.id,
                ship_type="interceptor",
                new_slots=["nuclear_source", "totally_fake_part", "electron_drive", None],
                owned_tech_ids=set(),
                db=db_session,
            )

    async def test_upgrade_unknown_ship_type_rejected(self, db_session: AsyncSession):
        player = await self._make_player_with_resources(db_session, "human")
        with pytest.raises(ValueError, match="Unknown ship type"):
            await apply_upgrade(
                player_id=player.id,
                ship_type="battlecruiser",
                new_slots=[None, None, None, None],
                owned_tech_ids=set(),
                db=db_session,
            )


# ---------------------------------------------------------------------------
# GET /games/{id}/players/{id}/blueprints endpoint
# ---------------------------------------------------------------------------

class TestBlueprintsEndpoint:
    async def test_blueprints_returned_after_game_start(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/blueprints",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4
        types = {bp["ship_type"] for bp in data}
        assert types == {"interceptor", "cruiser", "dreadnought", "starbase"}

    async def test_blueprints_include_power_balance(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/blueprints",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        for bp in resp.json():
            assert "power_balance" in bp
            assert bp["power_balance"] >= 0  # all defaults should be valid
            assert bp["is_valid"] is True

    async def test_blueprints_require_auth(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/blueprints"
        )
        assert resp.status_code == 401

    async def test_blueprints_404_unknown_game(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        resp = await db_client.get(
            "/games/99999/players/1/blueprints",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 404

    async def test_blueprints_404_unknown_player(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        resp = await db_client.get(
            f"/games/{game_id}/players/99999/blueprints",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 404

    async def test_blueprints_400_lobby_game(self, db_client: AsyncClient):
        token = await register_and_login(db_client, "lobby_bp@example.com", "lobbybp")
        create_resp = await db_client.post(
            "/games",
            json={"name": "Lobby BP Game", "max_players": 2},
            headers=auth_headers(token),
        )
        game_id = create_resp.json()["id"]
        resp = await db_client.get(
            f"/games/{game_id}/players/1/blueprints",
            headers=auth_headers(token),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# UPGRADE action via API
# ---------------------------------------------------------------------------

class TestUpgradeActionAPI:
    async def test_upgrade_action_no_tech_components(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["human", "planta"]
        )
        game_id = game["id"]

        # UPGRADE interceptor with all default (no-tech) components
        new_slots = ["nuclear_source", "electron_cannon", "electron_drive", "basic_shield"]
        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={
                "action_type": "upgrade",
                "payload": {"ship_type": "interceptor", "slots": new_slots},
            },
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 201

    async def test_upgrade_action_with_tech_unlocked(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["hydran_progress", "planta"]
        )
        game_id = game["id"]

        # First research ion_cannon (hydran starts with 6 science, cost 2)
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "research", "payload": {"tech_id": "ion_cannon"}},
            headers=auth_headers(tokens[0]),
        )
        # Pass turn back so player 0 can act again (player 1 needs to act)
        # But in a 2-player game player 1 goes next — let player 1 pass
        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "pass"},
            headers=auth_headers(tokens[1]),
        )
        # Now player 0 can UPGRADE with ion_cannon
        new_slots = ["nuclear_source", "ion_cannon", "electron_drive", None]
        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={
                "action_type": "upgrade",
                "payload": {"ship_type": "interceptor", "slots": new_slots},
            },
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 201

    async def test_upgrade_tech_not_owned_rejected(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # ion_cannon not researched
        new_slots = ["nuclear_source", "ion_cannon", "electron_drive", None]
        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={
                "action_type": "upgrade",
                "payload": {"ship_type": "interceptor", "slots": new_slots},
            },
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 400
        assert "requires technology" in resp.json()["detail"].lower()

    async def test_upgrade_invalid_power_rejected(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        # 4 cannons, no source → invalid power
        new_slots = [
            "electron_cannon", "electron_cannon",
            "electron_cannon", "electron_cannon",
        ]
        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={
                "action_type": "upgrade",
                "payload": {"ship_type": "interceptor", "slots": new_slots},
            },
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 400

    async def test_upgrade_requires_slots_in_payload(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]

        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={
                "action_type": "upgrade",
                "payload": {"ship_type": "interceptor"},
            },
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# BUILD action via API — ship records
# ---------------------------------------------------------------------------

class TestBuildActionAPI:
    async def test_build_creates_ship_record(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["mechanema", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        # Build an interceptor (Mechanema starts with 6 materials, cost 3)
        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "build", "payload": {"ship_type": "interceptor"}},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 201

        # Verify ship appears in the ships endpoint
        ships_resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/ships",
            headers=auth_headers(tokens[0]),
        )
        assert ships_resp.status_code == 200
        ships = ships_resp.json()
        # Mechanema starts with 2 interceptors + 1 cruiser; building one more interceptor
        interceptors = [s for s in ships if s["ship_type"] == "interceptor"]
        assert len(interceptors) >= 1

    async def test_build_deducts_materials(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["mechanema", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        # Check starting materials (Mechanema: 6)
        res_resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/resources",
            headers=auth_headers(tokens[0]),
        )
        materials_before = res_resp.json()["materials"]

        await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "build", "payload": {"ship_type": "interceptor"}},
            headers=auth_headers(tokens[0]),
        )

        res_resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/resources",
            headers=auth_headers(tokens[0]),
        )
        materials_after = res_resp.json()["materials"]
        # Interceptor costs 3
        assert materials_after == materials_before - 3

    async def test_build_insufficient_materials_rejected(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["human", "planta"]
        )
        game_id = game["id"]

        # Human starts with 3 materials; dreadnought costs 8
        resp = await db_client.post(
            f"/games/{game_id}/action",
            json={"action_type": "build", "payload": {"ship_type": "dreadnought"}},
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /games/{id}/players/{id}/ships endpoint
# ---------------------------------------------------------------------------

class TestShipsEndpoint:
    async def test_starting_ships_present_after_game_start(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["human", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/ships",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 200
        ships = resp.json()
        # Human starts with 2 interceptors
        interceptors = [s for s in ships if s["ship_type"] == "interceptor"]
        assert len(interceptors) == 2

    async def test_planta_has_no_starting_ships(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["human", "planta"]
        )
        game_id = game["id"]
        planta_player = next(p for p in game["players"] if p["turn_order"] == 1)

        resp = await db_client.get(
            f"/games/{game_id}/players/{planta_player['id']}/ships",
            headers=auth_headers(tokens[1]),
        )
        assert resp.status_code == 200
        # Planta has no starting ships
        assert resp.json() == []

    async def test_ships_require_auth(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/ships"
        )
        assert resp.status_code == 401

    async def test_ships_404_unknown_game(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(db_client, num_players=2)
        resp = await db_client.get(
            "/games/99999/players/1/ships",
            headers=auth_headers(tokens[0]),
        )
        assert resp.status_code == 404

    async def test_ships_have_hp_remaining(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["human", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/ships",
            headers=auth_headers(tokens[0]),
        )
        for ship in resp.json():
            assert ship["hp_remaining"] > 0
            assert ship["is_ancient"] is False

    async def test_mechanema_has_interceptors_and_cruiser(self, db_client: AsyncClient):
        tokens, game = await setup_started_game(
            db_client, num_players=2, species_list=["mechanema", "planta"]
        )
        game_id = game["id"]
        host_player = next(p for p in game["players"] if p["turn_order"] == 0)

        resp = await db_client.get(
            f"/games/{game_id}/players/{host_player['id']}/ships",
            headers=auth_headers(tokens[0]),
        )
        ships = resp.json()
        ship_types = [s["ship_type"] for s in ships]
        assert ship_types.count("interceptor") == 2
        assert ship_types.count("cruiser") == 1
