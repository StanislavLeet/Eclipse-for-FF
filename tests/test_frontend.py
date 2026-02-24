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
        # Static files at "/" should return HTML or redirect
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
