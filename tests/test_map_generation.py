"""Tests for galaxy map generation (Task 5)."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hex_tile import HexTile, TileType
from app.models.system import System
from app.services.map_generator import (
    effective_wormholes,
    hex_ring,
    tiles_share_wormhole,
)
from app.data.system_tiles import (
    GALACTIC_CENTER,
    SystemTile,
)


# ---------------------------------------------------------------------------
# Pure unit tests for the hex grid helpers
# ---------------------------------------------------------------------------

class TestHexRing:
    def test_ring_0_is_just_center(self):
        result = hex_ring(0, 0, 0)
        assert result == [(0, 0)]

    def test_ring_1_has_6_tiles(self):
        result = hex_ring(0, 0, 1)
        assert len(result) == 6

    def test_ring_2_has_12_tiles(self):
        result = hex_ring(0, 0, 2)
        assert len(result) == 12

    def test_ring_3_has_18_tiles(self):
        result = hex_ring(0, 0, 3)
        assert len(result) == 18

    def test_ring_1_all_distance_1(self):
        """All ring-1 tiles should be exactly 1 axial step from the origin."""
        for q, r in hex_ring(0, 0, 1):
            dist = (abs(q) + abs(r) + abs(q + r)) // 2
            assert dist == 1, f"Tile ({q},{r}) has distance {dist}, expected 1"

    def test_ring_2_all_distance_2(self):
        for q, r in hex_ring(0, 0, 2):
            dist = (abs(q) + abs(r) + abs(q + r)) // 2
            assert dist == 2

    def test_ring_3_all_distance_3(self):
        for q, r in hex_ring(0, 0, 3):
            dist = (abs(q) + abs(r) + abs(q + r)) // 2
            assert dist == 3

    def test_ring_1_no_duplicates(self):
        result = hex_ring(0, 0, 1)
        assert len(result) == len(set(result))

    def test_ring_2_no_duplicates(self):
        result = hex_ring(0, 0, 2)
        assert len(result) == len(set(result))

    def test_ring_3_no_duplicates(self):
        result = hex_ring(0, 0, 3)
        assert len(result) == len(set(result))

    def test_rings_are_disjoint(self):
        r1 = set(hex_ring(0, 0, 1))
        r2 = set(hex_ring(0, 0, 2))
        r3 = set(hex_ring(0, 0, 3))
        assert r1.isdisjoint(r2)
        assert r1.isdisjoint(r3)
        assert r2.isdisjoint(r3)

    def test_offset_center(self):
        result = hex_ring(2, -1, 1)
        assert len(result) == 6
        for q, r in result:
            dist = (abs(q - 2) + abs(r + 1) + abs((q - 2) + (r + 1))) // 2
            assert dist == 1


class TestEffectiveWormholes:
    def test_no_rotation(self):
        tile = SystemTile("T1", "Test", "inner", wormholes=[0, 3])
        assert effective_wormholes(tile, 0) == {0, 3}

    def test_rotation_1(self):
        tile = SystemTile("T1", "Test", "inner", wormholes=[0, 3])
        # Rotating by 1: 0→1, 3→4
        assert effective_wormholes(tile, 1) == {1, 4}

    def test_rotation_3(self):
        tile = SystemTile("T1", "Test", "inner", wormholes=[0, 3])
        # Rotating by 3: 0→3, 3→0 (same set)
        assert effective_wormholes(tile, 3) == {3, 0}

    def test_full_rotation_equals_original(self):
        tile = SystemTile("T1", "Test", "inner", wormholes=[1, 2, 4])
        assert effective_wormholes(tile, 6) == effective_wormholes(tile, 0)


class TestTilesShareWormhole:
    def test_aligned_wormholes(self):
        # From A to B is direction 3 (West): A needs wormhole dir 3, B needs dir 0
        tile_a = SystemTile("A", "A", "inner", wormholes=[3])  # wormhole toward W
        tile_b = SystemTile("B", "B", "inner", wormholes=[0])  # wormhole toward E
        # direction_a_to_b=3: A→B is West, so A needs wormhole 3, B needs wormhole 0
        assert tiles_share_wormhole(tile_a, 0, tile_b, 0, 3) is True

    def test_misaligned_wormholes(self):
        tile_a = SystemTile("A", "A", "inner", wormholes=[0])
        tile_b = SystemTile("B", "B", "inner", wormholes=[0])
        # Both have wormholes East, so they don't connect East-to-West
        assert tiles_share_wormhole(tile_a, 0, tile_b, 0, 0) is False

    def test_no_wormholes(self):
        tile_a = SystemTile("A", "A", "inner", wormholes=[])
        tile_b = SystemTile("B", "B", "inner", wormholes=[])
        assert tiles_share_wormhole(tile_a, 0, tile_b, 0, 0) is False

    def test_galactic_center_connects_all_directions(self):
        # GC has wormholes in all 6 directions. For each direction d, a neighbor
        # with a wormhole pointing back ((d+3)%6) should share the wormhole.
        for d in range(6):
            facing_back = (d + 3) % 6
            neighbor = SystemTile("I", "I", "inner", wormholes=[facing_back])
            assert tiles_share_wormhole(GALACTIC_CENTER, 0, neighbor, 0, d) is True


# ---------------------------------------------------------------------------
# Integration tests using the database
# ---------------------------------------------------------------------------

async def _setup_two_player_game(db_client: AsyncClient) -> tuple[str, str, dict]:
    """Register two players, create and start a game, return tokens and game data."""
    # Register host
    await db_client.post("/auth/register", json={"email": "mhost@example.com", "username": "mhost", "password": "pass123"})
    host_resp = await db_client.post("/auth/login", json={"email": "mhost@example.com", "password": "pass123"})
    host_token = host_resp.json()["access_token"]

    # Register player 2
    await db_client.post("/auth/register", json={"email": "mp2@example.com", "username": "mp2", "password": "pass123"})
    p2_resp = await db_client.post("/auth/login", json={"email": "mp2@example.com", "password": "pass123"})
    p2_token = p2_resp.json()["access_token"]

    def ah(t):
        return {"Authorization": f"Bearer {t}"}

    # Create game
    game_resp = await db_client.post(
        "/games", json={"name": "Map Test Game", "max_players": 2}, headers=ah(host_token)
    )
    game = game_resp.json()
    game_id = game["id"]

    # Invite and join
    inv = await db_client.post(
        f"/games/{game_id}/invite", json={"invitee_email": "mp2@example.com"}, headers=ah(host_token)
    )
    await db_client.post(
        f"/games/{game_id}/join", json={"token": inv.json()["token"]}, headers=ah(p2_token)
    )

    # Select species
    await db_client.post(f"/games/{game_id}/select-species", json={"species": "human"}, headers=ah(host_token))
    await db_client.post(f"/games/{game_id}/select-species", json={"species": "planta"}, headers=ah(p2_token))

    # Start game
    start = await db_client.post(f"/games/{game_id}/start", headers=ah(host_token))
    assert start.status_code == 200, start.text

    return host_token, p2_token, game


class TestMapGenerationForPlayerCounts:
    """Test map generation for different player counts via db."""

    async def _start_game_with_n_players(
        self, db_client: AsyncClient, n: int
    ) -> tuple[str, int]:
        """Helper: create and start a game with n players. Returns (host_token, game_id)."""
        species_list = [
            "human", "planta", "mechanema", "eridani_empire",
            "hydran_progress", "descendants_of_draco",
        ]
        tokens = []
        for i in range(n):
            email = f"u{n}_{i}@example.com"
            uname = f"u{n}i{i}"
            await db_client.post("/auth/register", json={"email": email, "username": uname, "password": "pw"})
            resp = await db_client.post("/auth/login", json={"email": email, "password": "pw"})
            tokens.append(resp.json()["access_token"])

        def ah(t):
            return {"Authorization": f"Bearer {t}"}

        game_resp = await db_client.post(
            "/games", json={"name": f"Game{n}P", "max_players": n}, headers=ah(tokens[0])
        )
        game_id = game_resp.json()["id"]

        for i in range(1, n):
            inv = await db_client.post(
                f"/games/{game_id}/invite",
                json={"invitee_email": f"u{n}_{i}@example.com"},
                headers=ah(tokens[0]),
            )
            await db_client.post(
                f"/games/{game_id}/join", json={"token": inv.json()["token"]}, headers=ah(tokens[i])
            )

        for i in range(n):
            await db_client.post(
                f"/games/{game_id}/select-species",
                json={"species": species_list[i]},
                headers=ah(tokens[i]),
            )

        start = await db_client.post(f"/games/{game_id}/start", headers=ah(tokens[0]))
        assert start.status_code == 200, start.text
        return tokens[0], game_id

    async def test_map_generated_on_start_2players(self, db_client: AsyncClient, db_session: AsyncSession):
        host_token, game_id = await self._start_game_with_n_players(db_client, 2)
        result = await db_session.execute(select(HexTile).where(HexTile.game_id == game_id))
        tiles = list(result.scalars().all())
        assert len(tiles) > 0

    async def test_tile_counts_2players(self, db_client: AsyncClient, db_session: AsyncSession):
        """2-player game: GC(1) + ring1(6) + 2 starting sectors(2) + ring2 remainder(10) + 2 homeworlds(2) = 21."""
        host_token, game_id = await self._start_game_with_n_players(db_client, 2)
        result = await db_session.execute(select(HexTile).where(HexTile.game_id == game_id))
        tiles = list(result.scalars().all())
        # GC + 6 inner + 2 starting sectors + 10 outer (ring2 remaining) + 2 homeworlds = 21
        assert len(tiles) == 21

    async def test_tile_counts_3players(self, db_client: AsyncClient, db_session: AsyncSession):
        """3P: GC(1) + ring1(6) + 3 SS + 9 outer(ring2) + 3 HW = 22."""
        host_token, game_id = await self._start_game_with_n_players(db_client, 3)
        result = await db_session.execute(select(HexTile).where(HexTile.game_id == game_id))
        tiles = list(result.scalars().all())
        assert len(tiles) == 22

    async def test_tile_counts_4players(self, db_client: AsyncClient, db_session: AsyncSession):
        """4P: GC(1) + ring1(6) + 4 SS + 8 outer(ring2) + 4 HW = 23."""
        host_token, game_id = await self._start_game_with_n_players(db_client, 4)
        result = await db_session.execute(select(HexTile).where(HexTile.game_id == game_id))
        tiles = list(result.scalars().all())
        assert len(tiles) == 23

    async def test_tile_counts_5players(self, db_client: AsyncClient, db_session: AsyncSession):
        """5P: GC(1) + ring1(6) + 5 SS + 7 outer(ring2) + 5 HW + 13 outer(ring3) = 37."""
        host_token, game_id = await self._start_game_with_n_players(db_client, 5)
        result = await db_session.execute(select(HexTile).where(HexTile.game_id == game_id))
        tiles = list(result.scalars().all())
        assert len(tiles) == 37

    async def test_tile_counts_6players(self, db_client: AsyncClient, db_session: AsyncSession):
        """6P: GC(1) + ring1(6) + 6 SS + 6 outer(ring2) + 6 HW + 12 outer(ring3) = 37."""
        host_token, game_id = await self._start_game_with_n_players(db_client, 6)
        result = await db_session.execute(select(HexTile).where(HexTile.game_id == game_id))
        tiles = list(result.scalars().all())
        assert len(tiles) == 37

    async def test_no_duplicate_positions(self, db_client: AsyncClient, db_session: AsyncSession):
        """No two tiles in the same game should share the same (q, r)."""
        _, game_id = await self._start_game_with_n_players(db_client, 2)
        result = await db_session.execute(select(HexTile).where(HexTile.game_id == game_id))
        tiles = list(result.scalars().all())
        positions = [(t.q, t.r) for t in tiles]
        assert len(positions) == len(set(positions)), "Duplicate tile positions found"

    async def test_galactic_center_at_origin(self, db_client: AsyncClient, db_session: AsyncSession):
        _, game_id = await self._start_game_with_n_players(db_client, 2)
        result = await db_session.execute(
            select(HexTile).where(
                HexTile.game_id == game_id,
                HexTile.tile_type == TileType.galactic_center,
            )
        )
        gc = result.scalar_one_or_none()
        assert gc is not None
        assert gc.q == 0
        assert gc.r == 0
        assert gc.is_explored is True

    async def test_homeworld_tiles_explored_and_owned(self, db_client: AsyncClient, db_session: AsyncSession):
        _, game_id = await self._start_game_with_n_players(db_client, 2)
        result = await db_session.execute(
            select(HexTile).where(
                HexTile.game_id == game_id,
                HexTile.tile_type == TileType.homeworld,
            )
        )
        homeworlds = list(result.scalars().all())
        assert len(homeworlds) == 2
        for hw in homeworlds:
            assert hw.is_explored is True
            assert hw.owner_player_id is not None

    async def test_starting_sectors_explored_and_owned(self, db_client: AsyncClient, db_session: AsyncSession):
        _, game_id = await self._start_game_with_n_players(db_client, 3)
        result = await db_session.execute(
            select(HexTile).where(
                HexTile.game_id == game_id,
                HexTile.tile_type == TileType.starting_sector,
            )
        )
        ss_tiles = list(result.scalars().all())
        assert len(ss_tiles) == 3
        for ss in ss_tiles:
            assert ss.is_explored is True
            assert ss.owner_player_id is not None

    async def test_inner_tiles_unexplored(self, db_client: AsyncClient, db_session: AsyncSession):
        _, game_id = await self._start_game_with_n_players(db_client, 2)
        result = await db_session.execute(
            select(HexTile).where(
                HexTile.game_id == game_id,
                HexTile.tile_type == TileType.inner,
            )
        )
        inner_tiles = list(result.scalars().all())
        assert len(inner_tiles) == 6
        for tile in inner_tiles:
            assert tile.is_explored is False

    async def test_system_records_for_explored_tiles(self, db_client: AsyncClient, db_session: AsyncSession):
        """All pre-explored tiles (GC, homeworlds, starting sectors) should have System records."""
        _, game_id = await self._start_game_with_n_players(db_client, 2)
        result = await db_session.execute(
            select(HexTile).where(
                HexTile.game_id == game_id,
                HexTile.is_explored.is_(True),
            )
        )
        explored_tiles = list(result.scalars().all())
        assert len(explored_tiles) == 5  # GC + 2 HW + 2 SS

        for tile in explored_tiles:
            sys_result = await db_session.execute(
                select(System).where(System.hex_tile_id == tile.id)
            )
            system = sys_result.scalar_one_or_none()
            assert system is not None, f"No System for explored tile id={tile.id} type={tile.tile_type}"

    async def test_homeworld_positions_at_ring3(self, db_client: AsyncClient, db_session: AsyncSession):
        """Homeworld tiles should be at axial distance 3 from origin."""
        _, game_id = await self._start_game_with_n_players(db_client, 2)
        result = await db_session.execute(
            select(HexTile).where(
                HexTile.game_id == game_id,
                HexTile.tile_type == TileType.homeworld,
            )
        )
        homeworlds = list(result.scalars().all())
        for hw in homeworlds:
            dist = (abs(hw.q) + abs(hw.r) + abs(hw.q + hw.r)) // 2
            assert dist == 3, f"Homeworld at ({hw.q},{hw.r}) has distance {dist}, expected 3"

    async def test_starting_sector_positions_at_ring2(self, db_client: AsyncClient, db_session: AsyncSession):
        """Starting sector tiles should be at axial distance 2 from origin."""
        _, game_id = await self._start_game_with_n_players(db_client, 2)
        result = await db_session.execute(
            select(HexTile).where(
                HexTile.game_id == game_id,
                HexTile.tile_type == TileType.starting_sector,
            )
        )
        ss_tiles = list(result.scalars().all())
        for ss in ss_tiles:
            dist = (abs(ss.q) + abs(ss.r) + abs(ss.q + ss.r)) // 2
            assert dist == 2, f"Starting sector at ({ss.q},{ss.r}) has distance {dist}, expected 2"

    async def test_two_player_homeworlds_are_opposite(self, db_client: AsyncClient, db_session: AsyncSession):
        """In a 2-player game, homeworlds should be on opposite sides (spokes 0 and 3)."""
        _, game_id = await self._start_game_with_n_players(db_client, 2)
        result = await db_session.execute(
            select(HexTile).where(
                HexTile.game_id == game_id,
                HexTile.tile_type == TileType.homeworld,
            )
        )
        homeworlds = list(result.scalars().all())
        assert len(homeworlds) == 2
        q_sum = homeworlds[0].q + homeworlds[1].q
        r_sum = homeworlds[0].r + homeworlds[1].r
        assert q_sum == 0 and r_sum == 0, (
            f"2P homeworlds should sum to (0,0), got ({q_sum},{r_sum})"
        )


class TestGetMapEndpoint:
    async def test_map_unavailable_in_lobby(self, db_client: AsyncClient):
        await db_client.post("/auth/register", json={"email": "lm@example.com", "username": "lmuser", "password": "pw"})
        resp = await db_client.post("/auth/login", json={"email": "lm@example.com", "password": "pw"})
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        game_resp = await db_client.post("/games", json={"name": "Lobby Game"}, headers=headers)
        game_id = game_resp.json()["id"]

        map_resp = await db_client.get(f"/games/{game_id}/map", headers=headers)
        assert map_resp.status_code == 400
        assert "started" in map_resp.json()["detail"].lower()

    async def test_map_returns_tiles_after_start(self, db_client: AsyncClient):
        host_token, p2_token, game = await _setup_two_player_game(db_client)
        headers = {"Authorization": f"Bearer {host_token}"}
        map_resp = await db_client.get(f"/games/{game['id']}/map", headers=headers)
        assert map_resp.status_code == 200
        tiles = map_resp.json()
        assert len(tiles) > 0

    async def test_map_has_galactic_center(self, db_client: AsyncClient):
        host_token, p2_token, game = await _setup_two_player_game(db_client)
        headers = {"Authorization": f"Bearer {host_token}"}
        map_resp = await db_client.get(f"/games/{game['id']}/map", headers=headers)
        tiles = map_resp.json()

        gc_tiles = [t for t in tiles if t["tile_type"] == "galactic_center"]
        assert len(gc_tiles) == 1
        assert gc_tiles[0]["q"] == 0
        assert gc_tiles[0]["r"] == 0
        assert gc_tiles[0]["is_explored"] is True

    async def test_map_galactic_center_has_system(self, db_client: AsyncClient):
        host_token, p2_token, game = await _setup_two_player_game(db_client)
        headers = {"Authorization": f"Bearer {host_token}"}
        map_resp = await db_client.get(f"/games/{game['id']}/map", headers=headers)
        tiles = map_resp.json()

        gc = next(t for t in tiles if t["tile_type"] == "galactic_center")
        assert gc["system"] is not None
        assert gc["system"]["ancient_ships_count"] == 1  # GCDS

    async def test_map_requires_auth(self, db_client: AsyncClient):
        host_token, _, game = await _setup_two_player_game(db_client)
        map_resp = await db_client.get(f"/games/{game['id']}/map")
        assert map_resp.status_code == 401

    async def test_map_homeworlds_have_systems(self, db_client: AsyncClient):
        host_token, p2_token, game = await _setup_two_player_game(db_client)
        headers = {"Authorization": f"Bearer {host_token}"}
        map_resp = await db_client.get(f"/games/{game['id']}/map", headers=headers)
        tiles = map_resp.json()

        homeworlds = [t for t in tiles if t["tile_type"] == "homeworld"]
        assert len(homeworlds) == 2
        for hw in homeworlds:
            assert hw["system"] is not None
            assert hw["system"]["name"] is not None

    async def test_map_unexplored_tiles_have_no_system(self, db_client: AsyncClient):
        host_token, p2_token, game = await _setup_two_player_game(db_client)
        headers = {"Authorization": f"Bearer {host_token}"}
        map_resp = await db_client.get(f"/games/{game['id']}/map", headers=headers)
        tiles = map_resp.json()

        unexplored = [t for t in tiles if not t["is_explored"]]
        assert len(unexplored) > 0
        for t in unexplored:
            assert t["system"] is None


class TestWormholeAlignment:
    async def test_homeworld_wormhole_points_inward(self, db_client: AsyncClient, db_session: AsyncSession):
        """
        Homeworld at spoke 0 (East, position (3,0)) should have wormhole pointing
        toward the center (direction 3 = West after rotation 0).
        Homeworld at spoke 3 (West, position (-3,0)) should have wormhole pointing
        toward the center (direction 0 = East after rotation 3 applied to base dir 3).
        """
        host_token, _, game = await _setup_two_player_game(db_client)
        result = await db_session.execute(
            select(HexTile).where(
                HexTile.game_id == game["id"],
                HexTile.tile_type == TileType.homeworld,
            )
        )
        homeworlds = list(result.scalars().all())
        from app.data.system_tiles import ALL_TILES

        for hw in homeworlds:
            template = ALL_TILES[hw.tile_template_id]
            eff_wh = effective_wormholes(template, hw.rotation)
            # The inward direction from this homeworld's position is (spoke_idx + 3) % 6
            # spoke_idx = hw.rotation
            inward_dir = (hw.rotation + 3) % 6
            assert inward_dir in eff_wh, (
                f"Homeworld at ({hw.q},{hw.r}) rotation={hw.rotation} "
                f"does not have wormhole in inward direction {inward_dir}. "
                f"Effective wormholes: {eff_wh}"
            )

    async def test_starting_sector_wormholes_connect_both_ways(
        self, db_client: AsyncClient, db_session: AsyncSession
    ):
        """Starting sector should have wormholes in both inward and outward directions."""
        host_token, _, game = await _setup_two_player_game(db_client)
        result = await db_session.execute(
            select(HexTile).where(
                HexTile.game_id == game["id"],
                HexTile.tile_type == TileType.starting_sector,
            )
        )
        ss_tiles = list(result.scalars().all())
        from app.data.system_tiles import ALL_TILES

        for ss in ss_tiles:
            template = ALL_TILES[ss.tile_template_id]
            eff_wh = effective_wormholes(template, ss.rotation)
            inward_dir = (ss.rotation + 3) % 6
            outward_dir = ss.rotation
            assert inward_dir in eff_wh, (
                f"Starting sector at ({ss.q},{ss.r}) rotation={ss.rotation} "
                f"missing inward wormhole {inward_dir}"
            )
            assert outward_dir in eff_wh, (
                f"Starting sector at ({ss.q},{ss.r}) rotation={ss.rotation} "
                f"missing outward wormhole {outward_dir}"
            )
