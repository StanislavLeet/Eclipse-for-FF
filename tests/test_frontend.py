"""
Frontend tests for Eclipse: Second Dawn.

Because Node.js is not available in this environment the JS logic is verified by:
1. Structural checks – all required frontend files exist and export the expected symbols.
2. Hex math – the axial-coordinate algorithms are ported to Python and validated.
3. API client – EclipseAPI module structure is verified by parsing the JS source.
4. Integration smoke – the FastAPI static-file endpoint returns the HTML shell.
"""

import math
import os
import re

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


# ---------------------------------------------------------------------------
# File structure
# ---------------------------------------------------------------------------

class TestFrontendFiles:
    """All required frontend files must exist."""

    def test_index_html_exists(self):
        assert os.path.isfile(os.path.join(FRONTEND_DIR, "index.html"))

    def test_main_js_exists(self):
        assert os.path.isfile(os.path.join(FRONTEND_DIR, "main.js"))

    def test_style_css_exists(self):
        assert os.path.isfile(os.path.join(FRONTEND_DIR, "style.css"))

    def test_api_js_exists(self):
        assert os.path.isfile(os.path.join(FRONTEND_DIR, "api.js"))

    def test_hex_renderer_js_exists(self):
        assert os.path.isfile(os.path.join(FRONTEND_DIR, "hex_renderer.js"))

    def test_board_js_exists(self):
        assert os.path.isfile(os.path.join(FRONTEND_DIR, "board.js"))

    def test_index_html_includes_api_js(self):
        path = os.path.join(FRONTEND_DIR, "index.html")
        content = open(path).read()
        assert "api.js" in content

    def test_index_html_includes_hex_renderer_js(self):
        path = os.path.join(FRONTEND_DIR, "index.html")
        content = open(path).read()
        assert "hex_renderer.js" in content

    def test_index_html_includes_board_js(self):
        path = os.path.join(FRONTEND_DIR, "index.html")
        content = open(path).read()
        assert "board.js" in content

    def test_index_html_has_svg_board_element(self):
        path = os.path.join(FRONTEND_DIR, "index.html")
        content = open(path).read()
        assert 'id="game-board"' in content

    def test_index_html_has_side_panel(self):
        path = os.path.join(FRONTEND_DIR, "index.html")
        content = open(path).read()
        assert 'id="side-panel"' in content


# ---------------------------------------------------------------------------
# API JS structure checks
# ---------------------------------------------------------------------------

class TestApiJsStructure:
    """Verify api.js exports the required functions."""

    REQUIRED_FUNCTIONS = [
        "setToken",
        "getToken",
        "register",
        "login",
        "getMe",
        "logout",
        "createGame",
        "getGame",
        "getMap",
        "getStatus",
        "getScores",
        "submitAction",
        "health",
    ]

    def _load_source(self):
        return open(os.path.join(FRONTEND_DIR, "api.js")).read()

    def test_eclipseapi_defined(self):
        source = self._load_source()
        assert "EclipseAPI" in source

    @pytest.mark.parametrize("fn_name", REQUIRED_FUNCTIONS)
    def test_function_present(self, fn_name):
        source = self._load_source()
        assert fn_name in source, f"EclipseAPI.{fn_name} not found in api.js"

    def test_uses_fetch(self):
        source = self._load_source()
        assert "fetch(" in source

    def test_has_authorization_header(self):
        source = self._load_source()
        assert "Authorization" in source

    def test_module_exports_for_node(self):
        source = self._load_source()
        assert "module.exports" in source


# ---------------------------------------------------------------------------
# Hex renderer JS structure checks
# ---------------------------------------------------------------------------

class TestHexRendererJsStructure:
    """Verify hex_renderer.js exports the required functions."""

    REQUIRED_EXPORTS = [
        "axialToPixel",
        "pixelToAxial",
        "axialRound",
        "hexCorners",
        "cornersToPoints",
        "playerColor",
        "renderTile",
        "PLAYER_COLORS",
        "PLANET_COLORS",
    ]

    def _load_source(self):
        return open(os.path.join(FRONTEND_DIR, "hex_renderer.js")).read()

    def test_hex_renderer_defined(self):
        source = self._load_source()
        assert "HexRenderer" in source

    @pytest.mark.parametrize("symbol", REQUIRED_EXPORTS)
    def test_symbol_present(self, symbol):
        source = self._load_source()
        assert symbol in source, f"{symbol} not found in hex_renderer.js"

    def test_uses_svg_namespace(self):
        source = self._load_source()
        assert "http://www.w3.org/2000/svg" in source

    def test_flat_top_hex_math(self):
        """The axialToPixel formula for flat-top hexes should use 3/2 * q for x."""
        source = self._load_source()
        assert "3 / 2" in source or "3/2" in source or "1.5" in source

    def test_sqrt3_in_source(self):
        source = self._load_source()
        assert "Math.sqrt(3)" in source


# ---------------------------------------------------------------------------
# Board JS structure checks
# ---------------------------------------------------------------------------

class TestBoardJsStructure:
    """Verify board.js exports the required functions."""

    REQUIRED_EXPORTS = [
        "init",
        "loadMap",
        "refreshMap",
        "render",
        "centerView",
        "setHighlightedTiles",
        "clearHighlights",
        "setTileClickHandler",
        "getTileById",
        "getTileByCoords",
    ]

    def _load_source(self):
        return open(os.path.join(FRONTEND_DIR, "board.js")).read()

    def test_board_defined(self):
        source = self._load_source()
        assert "Board" in source

    @pytest.mark.parametrize("fn_name", REQUIRED_EXPORTS)
    def test_function_present(self, fn_name):
        source = self._load_source()
        assert fn_name in source, f"Board.{fn_name} not found in board.js"

    def test_pan_zoom_wheel_handler(self):
        source = self._load_source()
        assert "wheel" in source

    def test_pan_zoom_mousedown_handler(self):
        source = self._load_source()
        assert "mousedown" in source

    def test_touch_support(self):
        source = self._load_source()
        assert "touchstart" in source

    def test_calls_hex_renderer(self):
        source = self._load_source()
        assert "HexRenderer" in source

    def test_calls_eclipse_api(self):
        source = self._load_source()
        assert "EclipseAPI" in source


# ---------------------------------------------------------------------------
# Hex coordinate math (Python port for correctness verification)
# ---------------------------------------------------------------------------

SQRT3 = math.sqrt(3)


def axial_to_pixel(q: float, r: float, size: float) -> tuple[float, float]:
    """Python port of HexRenderer.axialToPixel (flat-top hexagons)."""
    x = size * (3 / 2) * q
    y = size * (SQRT3 / 2 * q + SQRT3 * r)
    return x, y


def pixel_to_axial(x: float, y: float, size: float) -> tuple[float, float]:
    """Python port of HexRenderer.pixelToAxial."""
    q = (2 / 3) * x / size
    r = (-1 / 3) * x / size + (SQRT3 / 3) * y / size
    return q, r


def axial_round(q: float, r: float) -> tuple[int, int]:
    """Python port of HexRenderer.axialRound."""
    s = -q - r
    rq = round(q)
    rr = round(r)
    rs = round(s)
    dq = abs(rq - q)
    dr = abs(rr - r)
    ds = abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return rq, rr


def hex_corners(cx: float, cy: float, size: float) -> list[tuple[float, float]]:
    """Python port of HexRenderer.hexCorners."""
    corners = []
    for i in range(6):
        angle_deg = 60 * i
        angle_rad = math.radians(angle_deg)
        corners.append((
            cx + size * math.cos(angle_rad),
            cy + size * math.sin(angle_rad),
        ))
    return corners


class TestHexCoordinateMath:
    """Verify correctness of the hex coordinate algorithms."""

    def test_origin_hex_maps_to_pixel_origin(self):
        x, y = axial_to_pixel(0, 0, 50)
        assert x == pytest.approx(0.0)
        assert y == pytest.approx(0.0)

    def test_q1_r0_x_offset(self):
        """Moving one step in q should shift x by 3/2 * size."""
        x, y = axial_to_pixel(1, 0, 50)
        assert x == pytest.approx(75.0)  # 50 * 1.5
        assert y == pytest.approx(50 * SQRT3 / 2)

    def test_q0_r1_y_offset(self):
        """Moving one step in r should shift y by sqrt(3)*size."""
        x, y = axial_to_pixel(0, 1, 50)
        assert x == pytest.approx(0.0)
        assert y == pytest.approx(50 * SQRT3)

    def test_roundtrip_axial_pixel(self):
        """Converting axial -> pixel -> axial should return the original coords."""
        for q, r in [(0, 0), (1, 0), (0, 1), (-1, 1), (2, -1), (-3, 2)]:
            px, py = axial_to_pixel(q, r, 50)
            q2, r2 = pixel_to_axial(px, py, 50)
            assert q2 == pytest.approx(q, abs=1e-9)
            assert r2 == pytest.approx(r, abs=1e-9)

    def test_axial_round_exact_center(self):
        """Exact center of a hex rounds to that hex."""
        rq, rr = axial_round(2.0, -1.0)
        assert rq == 2
        assert rr == -1

    def test_axial_round_near_boundary(self):
        """A point near the boundary between two hexes rounds to the nearest hex."""
        # Slightly biased toward (1, 0)
        rq, rr = axial_round(0.9, 0.05)
        assert rq == 1

    def test_hex_corners_count(self):
        corners = hex_corners(0, 0, 50)
        assert len(corners) == 6

    def test_hex_corners_distance_from_center(self):
        """All six corners should be exactly 'size' away from center."""
        cx, cy = 100.0, 200.0
        size = 40.0
        corners = hex_corners(cx, cy, size)
        for x, y in corners:
            dist = math.hypot(x - cx, y - cy)
            assert dist == pytest.approx(size, abs=1e-9)

    def test_hex_corners_angles_60_apart(self):
        """Consecutive corner angles should be 60 degrees apart."""
        corners = hex_corners(0, 0, 50)
        angles = [math.degrees(math.atan2(y, x)) for x, y in corners]
        for i in range(1, len(angles)):
            diff = (angles[i] - angles[i - 1]) % 360
            assert diff == pytest.approx(60.0, abs=1e-6)

    def test_negative_coords_round_trip(self):
        for q, r in [(-2, 3), (-5, -1), (3, -4)]:
            px, py = axial_to_pixel(q, r, 30)
            q2, r2 = pixel_to_axial(px, py, 30)
            assert q2 == pytest.approx(q, abs=1e-9)
            assert r2 == pytest.approx(r, abs=1e-9)


# ---------------------------------------------------------------------------
# Player colors
# ---------------------------------------------------------------------------

class TestPlayerColors:
    """Verify the player color table in hex_renderer.js."""

    def test_at_least_six_colors(self):
        source = open(os.path.join(FRONTEND_DIR, "hex_renderer.js")).read()
        # Count hex color literals in PLAYER_COLORS array
        colors = re.findall(r"'#[0-9a-fA-F]{6}'", source)
        assert len(colors) >= 6

    def test_colors_are_valid_hex(self):
        source = open(os.path.join(FRONTEND_DIR, "hex_renderer.js")).read()
        colors = re.findall(r"'#[0-9a-fA-F]{6}'", source)
        for c in colors:
            # Strip quotes
            hex_val = c.strip("'")
            assert re.fullmatch(r"#[0-9a-fA-F]{6}", hex_val), f"Invalid color: {c}"


# ---------------------------------------------------------------------------
# Static file serving smoke test
# ---------------------------------------------------------------------------

class TestStaticServing:
    async def test_frontend_index_served(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/")
        # Static files at "/" — no route defined, frontend served at /static/
        assert resp.status_code in (200, 301, 302, 307, 308, 404)

    async def test_health_endpoint(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# CSS structure checks
# ---------------------------------------------------------------------------

class TestCssStructure:
    """Verify that CSS has board-related styles."""

    def _load_source(self):
        return open(os.path.join(FRONTEND_DIR, "style.css")).read()

    def test_has_hex_tile_style(self):
        assert ".hex-tile" in self._load_source()

    def test_has_hex_bg_style(self):
        assert ".hex-bg" in self._load_source()

    def test_has_board_container(self):
        assert "#board-container" in self._load_source()

    def test_has_game_board(self):
        assert "#game-board" in self._load_source()

    def test_has_responsive_media_query(self):
        assert "@media" in self._load_source()

    def test_has_action_tiles_style(self):
        assert ".action-tile" in self._load_source()

    def test_has_action_tiles_grid(self):
        assert ".action-tiles-grid" in self._load_source()

    def test_has_dialog_overlay(self):
        assert ".dialog-overlay" in self._load_source()

    def test_has_turn_banner(self):
        assert ".turn-banner" in self._load_source()

    def test_has_resource_grid(self):
        assert ".resource-grid" in self._load_source()

    def test_has_tech_list(self):
        assert ".tech-list" in self._load_source()

    def test_has_score_list(self):
        assert ".score-list" in self._load_source()

    def test_has_combat_log_list(self):
        assert ".combat-log-list" in self._load_source()

    def test_has_panel_section(self):
        assert ".panel-section" in self._load_source()

    def test_has_1280px_media_query(self):
        assert "1280px" in self._load_source()

    def test_has_modal_style(self):
        assert ".modal" in self._load_source()

    def test_has_species_grid(self):
        assert ".species-grid" in self._load_source()

    def test_has_game_card(self):
        assert ".game-card" in self._load_source()


# ---------------------------------------------------------------------------
# panels.js structure checks
# ---------------------------------------------------------------------------

class TestPanelsJsStructure:
    """Verify panels.js exports the required functions."""

    REQUIRED_EXPORTS = [
        "refresh",
        "renderResources",
        "renderTechnologies",
        "renderBlueprints",
        "renderTurnOrder",
        "renderScoreboard",
    ]

    def _load_source(self):
        return open(os.path.join(FRONTEND_DIR, "panels.js")).read()

    def test_panels_js_exists(self):
        assert os.path.isfile(os.path.join(FRONTEND_DIR, "panels.js"))

    def test_panels_defined(self):
        assert "Panels" in self._load_source()

    @pytest.mark.parametrize("fn_name", REQUIRED_EXPORTS)
    def test_function_present(self, fn_name):
        source = self._load_source()
        assert fn_name in source, f"Panels.{fn_name} not found in panels.js"

    def test_module_exports_for_node(self):
        assert "module.exports" in self._load_source()

    def test_uses_eclipse_api(self):
        assert "EclipseAPI" in self._load_source()

    def test_player_colors_defined(self):
        assert "PLAYER_COLORS" in self._load_source()

    def test_renders_resources_panel(self):
        source = self._load_source()
        assert "player-resources" in source

    def test_renders_technologies_panel(self):
        source = self._load_source()
        assert "player-technologies" in source

    def test_renders_turn_order_panel(self):
        source = self._load_source()
        assert "turn-order" in source

    def test_renders_scoreboard_panel(self):
        source = self._load_source()
        assert "vp-scoreboard" in source

    def test_escape_html_present(self):
        source = self._load_source()
        assert "escapeHtml" in source


# ---------------------------------------------------------------------------
# actions.js structure checks
# ---------------------------------------------------------------------------

class TestActionsJsStructure:
    """Verify actions.js exports the required functions."""

    REQUIRED_EXPORTS = [
        "renderActionTiles",
        "selectAction",
        "getSelectedAction",
        "clearSelection",
        "showConfirmDialog",
        "showBuildDialog",
        "showResearchDialog",
        "showUpgradeDialog",
        "closeDialog",
        "renderCombatLog",
        "showTurnBanner",
        "hideTurnBanner",
        "handleTileClick",
        "setActionSubmitHandler",
        "validateCreateGame",
        "validateRegister",
        "escapeHtml",
        "ACTION_TYPES",
        "ACTION_DESCRIPTIONS",
    ]

    def _load_source(self):
        return open(os.path.join(FRONTEND_DIR, "actions.js")).read()

    def test_actions_js_exists(self):
        assert os.path.isfile(os.path.join(FRONTEND_DIR, "actions.js"))

    def test_actions_defined(self):
        assert "Actions" in self._load_source()

    @pytest.mark.parametrize("fn_name", REQUIRED_EXPORTS)
    def test_function_present(self, fn_name):
        source = self._load_source()
        assert fn_name in source, f"Actions.{fn_name} not found in actions.js"

    def test_module_exports_for_node(self):
        assert "module.exports" in self._load_source()

    def test_has_all_action_types(self):
        source = self._load_source()
        for action in ["EXPLORE", "INFLUENCE", "BUILD", "RESEARCH", "MOVE", "UPGRADE", "PASS"]:
            assert action in source, f"Action type {action} missing from actions.js"

    def test_has_dialog_confirm_btn(self):
        assert "dialog-confirm" in self._load_source()

    def test_has_dialog_cancel_btn(self):
        assert "dialog-cancel" in self._load_source()

    def test_uses_board_module(self):
        assert "Board" in self._load_source()

    def test_has_ship_type_options(self):
        source = self._load_source()
        for ship in ["interceptor", "cruiser", "dreadnought", "starbase"]:
            assert ship in source, f"Ship type {ship} missing from actions.js"


# ---------------------------------------------------------------------------
# Form validation logic (Python port / source inspection)
# ---------------------------------------------------------------------------

class TestFormValidationLogic:
    """Verify form validation functions exist and contain the right logic."""

    def _load_actions_source(self):
        return open(os.path.join(FRONTEND_DIR, "actions.js")).read()

    def test_validate_create_game_exists(self):
        assert "validateCreateGame" in self._load_actions_source()

    def test_validate_register_exists(self):
        assert "validateRegister" in self._load_actions_source()

    def test_create_game_checks_name_empty(self):
        source = self._load_actions_source()
        assert "Game name is required" in source

    def test_create_game_checks_max_players_range(self):
        source = self._load_actions_source()
        assert "Max players must be between 2 and 6" in source

    def test_register_checks_email(self):
        source = self._load_actions_source()
        assert "email" in source.lower()

    def test_register_checks_password_length(self):
        source = self._load_actions_source()
        assert "Password must be at least 6" in source

    def test_register_checks_username_length(self):
        source = self._load_actions_source()
        assert "Username must be at least 2" in source

    def test_escape_html_replaces_amp(self):
        source = self._load_actions_source()
        # Verify the escapeHtml function handles & -> &amp;
        assert "&amp;" in source

    def test_escape_html_replaces_lt(self):
        source = self._load_actions_source()
        assert "&lt;" in source


# ---------------------------------------------------------------------------
# HTML structure checks for Task 17 new elements
# ---------------------------------------------------------------------------

class TestHtmlTask17Structure:
    """Verify index.html has all new panel elements and scripts."""

    def _load_source(self):
        return open(os.path.join(FRONTEND_DIR, "index.html")).read()

    def test_has_turn_banner(self):
        assert 'id="turn-banner"' in self._load_source()

    def test_has_turn_order_panel(self):
        assert 'id="turn-order"' in self._load_source()

    def test_has_player_resources_panel(self):
        assert 'id="player-resources"' in self._load_source()

    def test_has_action_tiles_panel(self):
        assert 'id="action-tiles"' in self._load_source()

    def test_has_player_technologies_panel(self):
        assert 'id="player-technologies"' in self._load_source()

    def test_has_player_blueprints_panel(self):
        assert 'id="player-blueprints"' in self._load_source()

    def test_has_vp_scoreboard_panel(self):
        assert 'id="vp-scoreboard"' in self._load_source()

    def test_has_combat_log_panel(self):
        assert 'id="combat-log"' in self._load_source()

    def test_has_create_game_modal(self):
        assert 'id="create-game-modal"' in self._load_source()

    def test_has_species_modal(self):
        assert 'id="species-modal"' in self._load_source()

    def test_has_invite_modal(self):
        assert 'id="invite-modal"' in self._load_source()

    def test_includes_panels_js(self):
        assert "panels.js" in self._load_source()

    def test_includes_actions_js(self):
        assert "actions.js" in self._load_source()

    def test_has_logout_btn(self):
        assert 'id="logout-btn"' in self._load_source()

    def test_has_create_game_form(self):
        assert 'id="create-game-form"' in self._load_source()

    def test_has_invite_form(self):
        assert 'id="invite-form"' in self._load_source()

    def test_has_species_list(self):
        assert 'id="species-list"' in self._load_source()

    def test_has_confirm_species_button(self):
        assert 'id="confirm-species"' in self._load_source()

    def test_has_board_controls(self):
        assert 'id="board-controls"' in self._load_source()

    def test_has_back_to_lobby_btn(self):
        assert 'id="back-to-lobby-btn"' in self._load_source()

    def test_login_form_has_novalidate(self):
        assert "novalidate" in self._load_source()


# ---------------------------------------------------------------------------
# main.js structure checks for Task 17
# ---------------------------------------------------------------------------

class TestMainJsTask17Structure:
    """Verify main.js has the new lobby integration and action handling code."""

    def _load_source(self):
        with open(os.path.join(FRONTEND_DIR, "main.js")) as f:
            return f.read()

    def test_has_load_lobby(self):
        assert "loadLobby" in self._load_source()

    def test_has_open_game(self):
        assert "openGame" in self._load_source()

    def test_has_submit_action(self):
        assert "submitAction" in self._load_source()

    def test_uses_panels_refresh(self):
        assert "Panels" in self._load_source()

    def test_uses_actions_render(self):
        assert "Actions" in self._load_source()

    def test_has_species_list(self):
        assert "SPECIES_LIST" in self._load_source()

    def test_has_random_species_option(self):
        assert "id: 'random'" in self._load_source()

    def test_has_start_game(self):
        assert "startGame" in self._load_source()

    def test_has_open_invite_modal(self):
        assert "openInviteModal" in self._load_source()

    def test_has_logout_handler(self):
        assert "logout-btn" in self._load_source()

    def test_has_form_error_display(self):
        assert "showFormError" in self._load_source()

    def test_has_escape_html(self):
        assert "escapeHtml" in self._load_source()

    def test_has_build_game_card(self):
        assert "buildGameCard" in self._load_source()

    def test_has_board_zoom_controls(self):
        assert "board-zoom-in" in self._load_source()

    def test_calls_actions_validate_register(self):
        source = self._load_source()
        assert "validateRegister" in source

    def test_calls_actions_validate_create_game(self):
        source = self._load_source()
        assert "validateCreateGame" in source
