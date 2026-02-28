// Eclipse: Second Dawn - Board Module
// Manages the interactive SVG game board: state, pan/zoom, rendering, and action highlighting.

const Board = (() => {
    // ---------------------------------------------------------------------------
    // State
    // ---------------------------------------------------------------------------
    const state = {
        gameId: null,
        tiles: [],           // raw tile data from API
        playerList: [],      // ordered list of players for color assignment
        playerIndexMap: {},  // player_id -> color index
        selectedAction: null,
        highlightedTileIds: new Set(),
        selectedTileId: null,

        // Pan/zoom
        panX: 0,
        panY: 0,
        zoom: 1,
        isPanning: false,
        panStart: { x: 0, y: 0 },
        panStartOffset: { x: 0, y: 0 },
    };

    // Layout constants
    const HEX_SIZE = 50; // circumradius in SVG units
    const SVG_PADDING = 100;

    // SVG element reference
    let svgEl = null;
    let transformGroup = null;

    // ---------------------------------------------------------------------------
    // Initialization
    // ---------------------------------------------------------------------------

    /**
     * Initialize the board on a given SVG element.
     * @param {SVGElement} svg
     */
    function init(svg) {
        svgEl = svg;

        // Create the transform group for pan/zoom
        transformGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        transformGroup.setAttribute('id', 'board-transform');
        svgEl.appendChild(transformGroup);

        // Attach pan/zoom handlers
        svgEl.addEventListener('wheel', onWheel, { passive: false });
        svgEl.addEventListener('mousedown', onMouseDown);
        svgEl.addEventListener('mousemove', onMouseMove);
        svgEl.addEventListener('mouseup', onMouseUp);
        svgEl.addEventListener('mouseleave', onMouseUp);

        // Touch support
        svgEl.addEventListener('touchstart', onTouchStart, { passive: false });
        svgEl.addEventListener('touchmove', onTouchMove, { passive: false });
        svgEl.addEventListener('touchend', onTouchEnd);
    }

    // ---------------------------------------------------------------------------
    // Data loading
    // ---------------------------------------------------------------------------

    /**
     * Load and render the map for a game.
     * @param {number} gameId
     * @param {Array}  players - ordered player list from game state
     */
    async function loadMap(gameId, players) {
        state.gameId = gameId;
        state.playerList = players || [];

        // Build index map: player_id -> position index (for color assignment)
        state.playerIndexMap = {};
        state.playerList.forEach((p, i) => {
            state.playerIndexMap[p.id] = i;
        });

        try {
            state.tiles = await EclipseAPI.getMap(gameId);
        } catch (err) {
            console.error('Failed to load map:', err);
            return;
        }

        render();
        centerView();
    }

    /**
     * Refresh the map without resetting pan/zoom.
     */
    async function refreshMap() {
        if (!state.gameId) return;
        try {
            state.tiles = await EclipseAPI.getMap(state.gameId);
        } catch (err) {
            console.error('Failed to refresh map:', err);
            return;
        }
        render();
    }

    // ---------------------------------------------------------------------------
    // Rendering
    // ---------------------------------------------------------------------------

    function render() {
        if (!transformGroup) return;

        // Clear existing tiles
        while (transformGroup.firstChild) {
            transformGroup.removeChild(transformGroup.firstChild);
        }

        for (const tile of state.tiles) {
            const { x, y } = HexRenderer.axialToPixel(tile.q, tile.r, HEX_SIZE);

            const highlighted = state.highlightedTileIds.has(tile.id);
            const selected = state.selectedTileId === tile.id;

            const tileGroup = HexRenderer.renderTile(tile, x, y, HEX_SIZE, {
                playerIndexMap: state.playerIndexMap,
                highlighted,
                selected,
            });

            // Click handler
            tileGroup.addEventListener('click', () => onTileClick(tile));
            tileGroup.style.cursor = 'pointer';

            transformGroup.appendChild(tileGroup);
        }

        applyTransform();
    }

    function applyTransform() {
        if (!transformGroup) return;
        transformGroup.setAttribute(
            'transform',
            `translate(${state.panX}, ${state.panY}) scale(${state.zoom})`
        );
    }

    /**
     * Center the board in the visible SVG area.
     */
    function centerView() {
        if (!svgEl || state.tiles.length === 0) return;

        const bbox = transformGroup.getBBox();
        const svgW = svgEl.clientWidth || svgEl.width.baseVal.value || 800;
        const svgH = svgEl.clientHeight || svgEl.height.baseVal.value || 600;

        state.zoom = Math.min(
            (svgW - SVG_PADDING * 2) / bbox.width,
            (svgH - SVG_PADDING * 2) / bbox.height,
            1.5
        );

        state.panX = svgW / 2 - (bbox.x + bbox.width / 2) * state.zoom;
        state.panY = svgH / 2 - (bbox.y + bbox.height / 2) * state.zoom;

        applyTransform();
    }

    // ---------------------------------------------------------------------------
    // Action highlighting
    // ---------------------------------------------------------------------------

    /**
     * Highlight tiles that are valid targets for the given action.
     * @param {string} actionType  - e.g. 'MOVE', 'EXPLORE', 'INFLUENCE'
     * @param {number[]} tileIds   - IDs of tiles to highlight
     */
    function setHighlightedTiles(actionType, tileIds) {
        state.selectedAction = actionType;
        state.highlightedTileIds = new Set(tileIds);
        state.selectedTileId = null;
        render();
    }

    /**
     * Clear all action highlights.
     */
    function clearHighlights() {
        state.selectedAction = null;
        state.highlightedTileIds = new Set();
        state.selectedTileId = null;
        render();
    }

    // ---------------------------------------------------------------------------
    // Tile click
    // ---------------------------------------------------------------------------

    let _onTileClickCallback = null;

    function onTileClick(tile) {
        if (state.isPanning) return;

        state.selectedTileId = tile.id;
        render();

        if (_onTileClickCallback) {
            _onTileClickCallback(tile, state.selectedAction);
        }
    }

    function setTileClickHandler(fn) {
        _onTileClickCallback = fn;
    }

    // ---------------------------------------------------------------------------
    // Pan and zoom handlers
    // ---------------------------------------------------------------------------

    function onWheel(e) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        const rect = svgEl.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // Zoom towards cursor position
        state.panX = mouseX - delta * (mouseX - state.panX);
        state.panY = mouseY - delta * (mouseY - state.panY);
        state.zoom = Math.max(0.2, Math.min(4, state.zoom * delta));

        applyTransform();
    }

    function onMouseDown(e) {
        if (e.button !== 0) return;
        state.isPanning = true;
        state.panStart = { x: e.clientX, y: e.clientY };
        state.panStartOffset = { x: state.panX, y: state.panY };
        svgEl.style.cursor = 'grabbing';
    }

    function onMouseMove(e) {
        if (!state.isPanning) return;
        state.panX = state.panStartOffset.x + (e.clientX - state.panStart.x);
        state.panY = state.panStartOffset.y + (e.clientY - state.panStart.y);
        applyTransform();
    }

    function onMouseUp() {
        state.isPanning = false;
        svgEl.style.cursor = '';
    }

    // Touch handling (pinch-to-zoom + single-finger pan)
    let _lastTouches = [];

    function onTouchStart(e) {
        e.preventDefault();
        _lastTouches = Array.from(e.touches).map(t => ({ x: t.clientX, y: t.clientY }));
        if (e.touches.length === 1) {
            state.isPanning = true;
            state.panStart = { x: e.touches[0].clientX, y: e.touches[0].clientY };
            state.panStartOffset = { x: state.panX, y: state.panY };
        }
    }

    function onTouchMove(e) {
        e.preventDefault();
        const touches = Array.from(e.touches).map(t => ({ x: t.clientX, y: t.clientY }));

        if (touches.length === 1 && state.isPanning) {
            state.panX = state.panStartOffset.x + (touches[0].x - state.panStart.x);
            state.panY = state.panStartOffset.y + (touches[0].y - state.panStart.y);
            applyTransform();
        } else if (touches.length === 2 && _lastTouches.length === 2) {
            const prevDist = Math.hypot(
                _lastTouches[0].x - _lastTouches[1].x,
                _lastTouches[0].y - _lastTouches[1].y
            );
            const newDist = Math.hypot(
                touches[0].x - touches[1].x,
                touches[0].y - touches[1].y
            );
            const delta = prevDist > 0 ? newDist / prevDist : 1;
            state.zoom = Math.max(0.2, Math.min(4, state.zoom * delta));
            applyTransform();
        }

        _lastTouches = touches;
    }

    function onTouchEnd() {
        state.isPanning = false;
        _lastTouches = [];
    }

    // ---------------------------------------------------------------------------
    // Utility: get tile by id
    // ---------------------------------------------------------------------------

    function getTileById(id) {
        return state.tiles.find(t => t.id === id) || null;
    }

    function getTileByCoords(q, r) {
        return state.tiles.find(t => t.q === q && t.r === r) || null;
    }

    // ---------------------------------------------------------------------------
    // Public API
    // ---------------------------------------------------------------------------
    return {
        init,
        loadMap,
        refreshMap,
        render,
        centerView,
        setHighlightedTiles,
        clearHighlights,
        setTileClickHandler,
        getTileById,
        getTileByCoords,
        // Expose state for testing
        _state: state,
    };
})();

// Export for Node.js test environments
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Board;
}
