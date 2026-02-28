// Eclipse: Second Dawn - Panels Module
// Manages sidebar panels: player resources, technologies, blueprints, turn order, scoreboard.

const Panels = (() => {
    const PLAYER_COLORS = [
        '#4488ff', '#ff4444', '#44cc44', '#ffcc44', '#cc44ff', '#ff8844',
    ];

    // ---------------------------------------------------------------------------
    // Resources Panel
    // ---------------------------------------------------------------------------

    async function renderResources(gameId, playerId) {
        const el = document.getElementById('player-resources');
        if (!el) return;

        try {
            const data = await EclipseAPI.getResources(gameId, playerId);
            const money = data.money ?? 0;
            const science = data.science ?? 0;
            const materials = data.materials ?? 0;
            const population = data.population_cubes ?? 0;

            el.innerHTML =
                '<h3>Resources</h3>' +
                '<div class="resource-grid">' +
                    '<div class="resource-item">' +
                        '<span class="resource-label">Money</span>' +
                        '<span class="resource-value money">' + money + '</span>' +
                    '</div>' +
                    '<div class="resource-item">' +
                        '<span class="resource-label">Science</span>' +
                        '<span class="resource-value science">' + science + '</span>' +
                    '</div>' +
                    '<div class="resource-item">' +
                        '<span class="resource-label">Materials</span>' +
                        '<span class="resource-value materials">' + materials + '</span>' +
                    '</div>' +
                    '<div class="resource-item">' +
                        '<span class="resource-label">Population</span>' +
                        '<span class="resource-value population">' + population + '</span>' +
                    '</div>' +
                '</div>';
        } catch (_err) {
            el.innerHTML = '<p class="panel-error">Resources unavailable</p>';
        }
    }

    // ---------------------------------------------------------------------------
    // Technologies Panel
    // ---------------------------------------------------------------------------

    async function renderTechnologies(gameId, playerId) {
        const el = document.getElementById('player-technologies');
        if (!el) return;

        try {
            const data = await EclipseAPI.getTechnologies(gameId, playerId);
            const techs = Array.isArray(data) ? data : (data.technologies || []);

            if (techs.length === 0) {
                el.innerHTML = '<h3>Technologies</h3><p class="panel-empty">No technologies researched</p>';
                return;
            }

            const items = techs.map(function (t) {
                const cat = (t.category || '').toLowerCase();
                const name = t.name || t.tech_id || 'Unknown';
                return '<div class="tech-item tech-' + cat + '">' +
                    '<span class="tech-name">' + escapeHtml(name) + '</span>' +
                    '<span class="tech-category">' + escapeHtml(t.category || '') + '</span>' +
                    '</div>';
            }).join('');

            el.innerHTML = '<h3>Technologies</h3><div class="tech-list">' + items + '</div>';
        } catch (_err) {
            el.innerHTML = '<p class="panel-error">Technologies unavailable</p>';
        }
    }

    // ---------------------------------------------------------------------------
    // Blueprints Panel
    // ---------------------------------------------------------------------------

    function renderBlueprints(blueprints) {
        const el = document.getElementById('player-blueprints');
        if (!el) return;

        if (!blueprints || blueprints.length === 0) {
            el.innerHTML = '<h3>Blueprints</h3><p class="panel-empty">No blueprints available</p>';
            return;
        }

        const items = blueprints.map(function (bp) {
            const type = bp.ship_type || '';
            const valid = bp.is_valid;
            return '<div class="blueprint-item">' +
                '<span class="blueprint-type">' + escapeHtml(type) + '</span>' +
                '<span class="blueprint-status ' + (valid ? 'valid' : 'invalid') + '">' +
                    (valid ? '✓' : '⚠') +
                '</span>' +
                '</div>';
        }).join('');

        el.innerHTML = '<h3>Blueprints</h3><div class="blueprint-list">' + items + '</div>';
    }

    // ---------------------------------------------------------------------------
    // Turn Order Panel
    // ---------------------------------------------------------------------------

    function renderTurnOrder(players, activePlayerId, currentUserId) {
        const el = document.getElementById('turn-order');
        if (!el) return;

        if (!players || players.length === 0) {
            el.innerHTML = '<h3>Turn Order</h3><p class="panel-empty">No players</p>';
            return;
        }

        const items = players.map(function (p, i) {
            const isActive = p.id === activePlayerId;
            const isMe = p.user_id === currentUserId || p.id === currentUserId;
            const color = PLAYER_COLORS[i % PLAYER_COLORS.length];
            const name = escapeHtml(p.username || p.species || 'Player ' + (i + 1));

            return '<div class="turn-order-item' +
                (isActive ? ' active-player' : '') +
                (isMe ? ' me' : '') + '">' +
                '<span class="player-color-dot" style="background:' + color + '"></span>' +
                '<span class="player-name">' + name + '</span>' +
                (isActive ? '<span class="active-label">&#9654;</span>' : '') +
                (p.has_passed ? '<span class="passed-label">PASS</span>' : '') +
                '</div>';
        }).join('');

        el.innerHTML = '<h3>Turn Order</h3><div class="turn-order-list">' + items + '</div>';
    }

    // ---------------------------------------------------------------------------
    // VP Scoreboard Panel
    // ---------------------------------------------------------------------------

    async function renderScoreboard(gameId) {
        const el = document.getElementById('vp-scoreboard');
        if (!el) return;

        try {
            const data = await EclipseAPI.getScores(gameId);
            const scores = Array.isArray(data) ? data : (data.scores || []);

            if (scores.length === 0) {
                el.innerHTML = '<h3>VP Standings</h3><p class="panel-empty">No scores yet</p>';
                return;
            }

            const sorted = scores.slice().sort(function (a, b) {
                return (b.total_vp || 0) - (a.total_vp || 0);
            });

            const items = sorted.map(function (s, i) {
                const name = escapeHtml(s.username || ('Player ' + (i + 1)));
                const vp = s.total_vp || 0;
                return '<div class="score-item rank-' + (i + 1) + '">' +
                    '<span class="score-rank">' + (i + 1) + '.</span>' +
                    '<span class="score-name">' + name + '</span>' +
                    '<span class="score-vp">' + vp + ' VP</span>' +
                    '</div>';
            }).join('');

            el.innerHTML = '<h3>VP Standings</h3><div class="score-list">' + items + '</div>';
        } catch (_err) {
            el.innerHTML = '<p class="panel-error">Scores unavailable</p>';
        }
    }

    // ---------------------------------------------------------------------------
    // Full panel refresh
    // ---------------------------------------------------------------------------

    async function refresh(gameId, playerId, gameState) {
        const players = (gameState && gameState.players) || [];
        const activeId = gameState && gameState.active_player_id;
        const currentUserId = gameState && gameState.current_user_id;

        renderTurnOrder(players, activeId, currentUserId);

        if (gameId) {
            await renderScoreboard(gameId);
        }

        if (gameId && playerId) {
            await renderResources(gameId, playerId);
            await renderTechnologies(gameId, playerId);
        }

        // Blueprints from player data in game state
        const me = players.find(function (p) { return p.id === playerId; });
        if (me && me.blueprints) {
            renderBlueprints(me.blueprints);
        }
    }

    // ---------------------------------------------------------------------------
    // Utility
    // ---------------------------------------------------------------------------

    function escapeHtml(str) {
        if (typeof str !== 'string') str = String(str);
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // ---------------------------------------------------------------------------
    // Public API
    // ---------------------------------------------------------------------------
    return {
        refresh,
        renderResources,
        renderTechnologies,
        renderBlueprints,
        renderTurnOrder,
        renderScoreboard,
    };
})();

if (typeof module !== 'undefined' && module.exports) {
    module.exports = Panels;
}
