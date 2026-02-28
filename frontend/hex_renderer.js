// Eclipse: Second Dawn - Hex Renderer
// Handles axial-coordinate math and SVG rendering for the game board.
// Uses flat-top hexagons.

const HexRenderer = (() => {
    // ---------------------------------------------------------------------------
    // Coordinate math (flat-top hexagons)
    // ---------------------------------------------------------------------------

    // Convert axial (q, r) to pixel (x, y) for a flat-top hex of given size.
    // Origin is at (0, 0).
    function axialToPixel(q, r, size) {
        const x = size * (3 / 2) * q;
        const y = size * (Math.sqrt(3) / 2 * q + Math.sqrt(3) * r);
        return { x, y };
    }

    // Convert pixel (x, y) back to fractional axial coordinates.
    function pixelToAxial(x, y, size) {
        const q = (2 / 3) * x / size;
        const r = (-1 / 3) * x / size + (Math.sqrt(3) / 3) * y / size;
        return { q, r };
    }

    // Round fractional axial to nearest hex.
    function axialRound(q, r) {
        const s = -q - r;
        let rq = Math.round(q);
        let rr = Math.round(r);
        let rs = Math.round(s);
        const dq = Math.abs(rq - q);
        const dr = Math.abs(rr - r);
        const ds = Math.abs(rs - s);
        if (dq > dr && dq > ds) {
            rq = -rr - rs;
        } else if (dr > ds) {
            rr = -rq - rs;
        }
        return { q: rq, r: rr };
    }

    // Returns the 6 corner pixel positions of a flat-top hex centered at (cx, cy).
    function hexCorners(cx, cy, size) {
        const corners = [];
        for (let i = 0; i < 6; i++) {
            const angleDeg = 60 * i; // flat-top: 0, 60, 120, …
            const angleRad = (Math.PI / 180) * angleDeg;
            corners.push({
                x: cx + size * Math.cos(angleRad),
                y: cy + size * Math.sin(angleRad),
            });
        }
        return corners;
    }

    // Build an SVG polygon points string from corners.
    function cornersToPoints(corners) {
        return corners.map(c => `${c.x.toFixed(2)},${c.y.toFixed(2)}`).join(' ');
    }

    // ---------------------------------------------------------------------------
    // Player colors
    // ---------------------------------------------------------------------------
    const PLAYER_COLORS = [
        '#4488ff', // blue
        '#ff4444', // red
        '#44cc44', // green
        '#ffcc44', // yellow
        '#cc44ff', // purple
        '#ff8844', // orange
    ];

    function playerColor(index) {
        return PLAYER_COLORS[index % PLAYER_COLORS.length];
    }

    // ---------------------------------------------------------------------------
    // SVG helpers
    // ---------------------------------------------------------------------------
    const SVG_NS = 'http://www.w3.org/2000/svg';

    function svgEl(tag, attrs = {}) {
        const el = document.createElementNS(SVG_NS, tag);
        for (const [k, v] of Object.entries(attrs)) {
            el.setAttribute(k, v);
        }
        return el;
    }

    // ---------------------------------------------------------------------------
    // Tile rendering
    // ---------------------------------------------------------------------------

    // Map tile_type string to display label.
    const TILE_TYPE_LABELS = {
        homeworld: 'HOME',
        inner: '',
        middle: '',
        outer: '',
        galactic_center: 'GC',
    };

    // Planet type color codes.
    const PLANET_COLORS = {
        money: '#ffdd44',
        science: '#44ddff',
        materials: '#ff8844',
        advanced: '#aa66ff',
        orbital: '#88ffcc',
    };

    /**
     * Render a single hex tile as an SVG <g> group element.
     *
     * @param {Object} tile   - Tile data from GET /games/{id}/map
     * @param {number} cx     - Center x in SVG coords
     * @param {number} cy     - Center y in SVG coords
     * @param {number} size   - Hex size (circumradius)
     * @param {Object} opts   - { playerIndexMap, highlighted, selected }
     */
    function renderTile(tile, cx, cy, size, opts = {}) {
        const { playerIndexMap = {}, highlighted = false, selected = false } = opts;

        const corners = hexCorners(cx, cy, size);
        const points = cornersToPoints(corners);

        const g = svgEl('g', {
            class: 'hex-tile',
            'data-q': tile.q,
            'data-r': tile.r,
            'data-tile-id': tile.id,
        });

        // Background polygon
        let fillColor = '#1a1a35';
        if (!tile.is_explored) {
            fillColor = '#0e0e22';
        } else if (tile.owner_player_id != null) {
            const idx = playerIndexMap[tile.owner_player_id] ?? 0;
            fillColor = playerColor(idx) + '33'; // 20% opacity tint
        }

        let strokeColor = '#334466';
        if (highlighted) strokeColor = '#ffcc44';
        if (selected) strokeColor = '#44ffcc';

        const hex = svgEl('polygon', {
            points,
            fill: fillColor,
            stroke: strokeColor,
            'stroke-width': highlighted || selected ? 2 : 1,
            class: 'hex-bg',
        });
        g.appendChild(hex);

        if (!tile.is_explored) {
            // Face-down tile: show a simple indicator
            const label = svgEl('text', {
                x: cx,
                y: cy,
                'text-anchor': 'middle',
                'dominant-baseline': 'central',
                fill: '#334466',
                'font-size': size * 0.25,
                class: 'hex-label',
            });
            label.textContent = '?';
            g.appendChild(label);
            return g;
        }

        // Explored tile
        const typeLabel = TILE_TYPE_LABELS[tile.tile_type] ?? '';
        if (typeLabel) {
            const typeText = svgEl('text', {
                x: cx,
                y: cy - size * 0.55,
                'text-anchor': 'middle',
                fill: '#aaaacc',
                'font-size': size * 0.2,
                class: 'hex-type-label',
            });
            typeText.textContent = typeLabel;
            g.appendChild(typeText);
        }

        // Planet slots
        const system = tile.system;
        if (system && system.planets) {
            renderPlanets(g, system.planets, cx, cy, size);
        }

        // Wormhole indicators
        if (system && system.wormholes) {
            renderWormholes(g, system.wormholes, cx, cy, size, tile.rotation || 0);
        }

        // Owner indicator (small colored dot in center)
        if (tile.owner_player_id != null) {
            const idx = playerIndexMap[tile.owner_player_id] ?? 0;
            g.appendChild(svgEl('circle', {
                cx,
                cy,
                r: size * 0.12,
                fill: playerColor(idx),
                opacity: 0.8,
                class: 'hex-owner',
            }));
        }

        // Ships
        if (tile.ships && tile.ships.length > 0) {
            renderShips(g, tile.ships, cx, cy, size, playerIndexMap);
        }

        return g;
    }

    /**
     * Render planet circles for a hex tile.
     * Planets are placed in a small arc below center.
     */
    function renderPlanets(g, planets, cx, cy, size) {
        const count = planets.length;
        if (count === 0) return;

        const spacing = size * 0.3;
        const startX = cx - ((count - 1) * spacing) / 2;
        const baseY = cy + size * 0.25;

        for (let i = 0; i < count; i++) {
            const planet = planets[i];
            const px = startX + i * spacing;
            const color = PLANET_COLORS[planet.type] ?? '#aaaaaa';

            g.appendChild(svgEl('circle', {
                cx: px,
                cy: baseY,
                r: size * 0.1,
                fill: color,
                stroke: '#ffffff',
                'stroke-width': 0.5,
                class: 'hex-planet',
                'data-planet-type': planet.type,
            }));

            // Population cube overlay (if colonized)
            if (planet.owner_player_id != null) {
                // Small square marker
                const sq = size * 0.08;
                g.appendChild(svgEl('rect', {
                    x: px - sq,
                    y: baseY - sq,
                    width: sq * 2,
                    height: sq * 2,
                    fill: '#ffffff',
                    opacity: 0.9,
                    class: 'hex-pop-cube',
                }));
            }
        }
    }

    /**
     * Render wormhole direction indicators as small triangles on hex edges.
     * wormholes is an array of integers 0-5 indicating which edge has a wormhole.
     * Edges are numbered 0-5 starting from the right and going clockwise for flat-top.
     * rotation shifts the edge indices.
     */
    function renderWormholes(g, wormholes, cx, cy, size, rotation) {
        for (const edge of wormholes) {
            const rotatedEdge = (edge + rotation) % 6;
            const angleDeg = 60 * rotatedEdge;
            const angleRad = (Math.PI / 180) * angleDeg;
            const dist = size * 0.8;
            const wx = cx + dist * Math.cos(angleRad);
            const wy = cy + dist * Math.sin(angleRad);

            g.appendChild(svgEl('circle', {
                cx: wx,
                cy: wy,
                r: size * 0.07,
                fill: '#88aaff',
                opacity: 0.85,
                class: 'hex-wormhole',
            }));
        }
    }

    /**
     * Render ship icons on a hex tile.
     * Ships belonging to the same player are grouped with a colored indicator.
     */
    function renderShips(g, ships, cx, cy, size, playerIndexMap) {
        // Group ships by player
        const byPlayer = {};
        for (const ship of ships) {
            const pid = ship.player_id ?? ship.owner_player_id ?? 'ancient';
            if (!byPlayer[pid]) byPlayer[pid] = [];
            byPlayer[pid].push(ship);
        }

        const playerIds = Object.keys(byPlayer);
        const offset = size * 0.3;
        const startX = cx - ((playerIds.length - 1) * offset) / 2;

        playerIds.forEach((pid, i) => {
            const shipList = byPlayer[pid];
            const sx = startX + i * offset;
            const sy = cy - size * 0.3;

            const color = pid === 'ancient'
                ? '#888888'
                : playerColor(playerIndexMap[parseInt(pid)] ?? i);

            // Draw a small ship triangle
            const half = size * 0.1;
            const points = `${sx},${sy - half} ${sx - half},${sy + half} ${sx + half},${sy + half}`;
            g.appendChild(svgEl('polygon', {
                points,
                fill: color,
                stroke: '#ffffff',
                'stroke-width': 0.5,
                class: 'hex-ship',
                'data-ship-count': shipList.length,
            }));

            if (shipList.length > 1) {
                const badge = svgEl('text', {
                    x: sx + half,
                    y: sy - half,
                    fill: '#ffffff',
                    'font-size': size * 0.18,
                    'text-anchor': 'middle',
                    class: 'hex-ship-count',
                });
                badge.textContent = shipList.length;
                g.appendChild(badge);
            }
        });
    }

    // ---------------------------------------------------------------------------
    // Public API
    // ---------------------------------------------------------------------------
    return {
        axialToPixel,
        pixelToAxial,
        axialRound,
        hexCorners,
        cornersToPoints,
        playerColor,
        renderTile,
        renderPlanets,
        renderWormholes,
        renderShips,
        PLAYER_COLORS,
        PLANET_COLORS,
    };
})();

// Export for Node.js test environments
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HexRenderer;
}
