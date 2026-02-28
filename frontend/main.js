// Eclipse: Second Dawn - Main Frontend Entry Point

const API_BASE = '';  // Same origin

// ---------------------------------------------------------------------------
// App state
// ---------------------------------------------------------------------------
const state = {
    token: localStorage.getItem('eclipse_token'),
    currentUser: null,
    currentGame: null,
    currentPlayerId: null,
    boardInitialized: false,
};

// ---------------------------------------------------------------------------
// Utility: API fetch with auth header
// ---------------------------------------------------------------------------
async function apiFetch(path, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...(state.token ? { 'Authorization': `Bearer ${state.token}` } : {}),
        ...options.headers,
    };

    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
}

// Keep EclipseAPI in sync with auth token
function syncApiToken() {
    if (typeof EclipseAPI !== 'undefined') {
        EclipseAPI.setToken(state.token);
    }
}

// ---------------------------------------------------------------------------
// Section navigation
// ---------------------------------------------------------------------------
function showSection(id) {
    ['loading-screen', 'auth-section', 'lobby-section', 'game-section'].forEach(function (sid) {
        const el = document.getElementById(sid);
        if (el) el.classList.toggle('hidden', sid !== id);
    });
}

function updateNavStatus(text) {
    const el = document.getElementById('nav-status');
    if (el) el.textContent = text;
}

function showFormError(elementId, message) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = message;
    el.classList.remove('hidden');
}

function clearFormError(elementId) {
    const el = document.getElementById(elementId);
    if (el) el.classList.add('hidden');
}

// ---------------------------------------------------------------------------
// Health check & initialization
// ---------------------------------------------------------------------------
async function checkHealth() {
    try {
        const data = await apiFetch('/health');
        return data.status === 'ok';
    } catch {
        return false;
    }
}

async function init() {
    const healthy = await checkHealth();
    if (!healthy) {
        const el = document.getElementById('loading-screen');
        if (el) el.textContent = 'Cannot connect to server.';
        return;
    }

    if (state.token) {
        try {
            state.currentUser = await apiFetch('/auth/me');
            updateNavStatus(`Logged in as ${state.currentUser.username}`);
            document.getElementById('logout-btn')?.classList.remove('hidden');
            await loadLobby();
            showSection('lobby-section');
        } catch {
            localStorage.removeItem('eclipse_token');
            state.token = null;
            syncApiToken();
            showSection('auth-section');
        }
    } else {
        showSection('auth-section');
    }
}

// ---------------------------------------------------------------------------
// Auth: login form
// ---------------------------------------------------------------------------
document.getElementById('login-form')?.addEventListener('submit', async function (e) {
    e.preventDefault();
    clearFormError('login-error');

    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;

    if (!email || !password) {
        showFormError('login-error', 'Email and password are required.');
        return;
    }

    try {
        const data = await apiFetch('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
        });

        state.token = data.access_token;
        localStorage.setItem('eclipse_token', state.token);
        syncApiToken();
        await init();
    } catch (err) {
        showFormError('login-error', `Login failed: ${err.message}`);
    }
});

// ---------------------------------------------------------------------------
// Auth: register form
// ---------------------------------------------------------------------------
document.getElementById('register-form')?.addEventListener('submit', async function (e) {
    e.preventDefault();
    clearFormError('register-error');

    const email = document.getElementById('reg-email').value.trim();
    const username = document.getElementById('reg-username').value.trim();
    const password = document.getElementById('reg-password').value;

    // Client-side validation
    if (typeof Actions !== 'undefined') {
        const result = Actions.validateRegister(email, username, password);
        if (!result.valid) {
            showFormError('register-error', result.errors.join(' '));
            return;
        }
    }

    try {
        await apiFetch('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ email, username, password }),
        });
        // Switch to login panel after successful registration
        document.getElementById('register-panel')?.classList.add('hidden');
        document.getElementById('login-panel')?.classList.remove('hidden');
        document.getElementById('login-email').value = email;
    } catch (err) {
        showFormError('register-error', `Registration failed: ${err.message}`);
    }
});

// ---------------------------------------------------------------------------
// Auth: panel toggles
// ---------------------------------------------------------------------------
document.getElementById('show-register')?.addEventListener('click', function (e) {
    e.preventDefault();
    document.getElementById('login-panel')?.classList.add('hidden');
    document.getElementById('register-panel')?.classList.remove('hidden');
});

document.getElementById('show-login')?.addEventListener('click', function (e) {
    e.preventDefault();
    document.getElementById('register-panel')?.classList.add('hidden');
    document.getElementById('login-panel')?.classList.remove('hidden');
});

// ---------------------------------------------------------------------------
// Auth: logout
// ---------------------------------------------------------------------------
document.getElementById('logout-btn')?.addEventListener('click', async function () {
    try {
        await apiFetch('/auth/logout', { method: 'POST' });
    } catch (_) { /* ignore */ }
    localStorage.removeItem('eclipse_token');
    state.token = null;
    state.currentUser = null;
    state.currentGame = null;
    state.currentPlayerId = null;
    syncApiToken();
    document.getElementById('logout-btn')?.classList.add('hidden');
    updateNavStatus('');
    showSection('auth-section');
});

// ---------------------------------------------------------------------------
// Lobby: load and render game list
// ---------------------------------------------------------------------------
async function loadLobby() {
    const listEl = document.getElementById('game-list');
    if (!listEl) return;
    listEl.innerHTML = '<p class="panel-empty">Loading games...</p>';

    try {
        const games = await apiFetch('/games');
        if (!games || games.length === 0) {
            listEl.innerHTML = '<p class="panel-empty">No games yet. Create one!</p>';
            return;
        }

        listEl.innerHTML = '';
        for (const game of games) {
            const card = buildGameCard(game);
            listEl.appendChild(card);
        }
    } catch (err) {
        listEl.innerHTML = `<p class="panel-error">Failed to load games: ${err.message}</p>`;
    }
}

function buildGameCard(game) {
    const card = document.createElement('div');
    card.className = 'game-card';

    const gameStatus = String(game.status || 'lobby').toLowerCase();
    const playerCount = (game.players || []).length;
    const statusClass = `game-status-${gameStatus}`;

    card.innerHTML =
        '<div class="game-card-info">' +
            `<div class="game-card-name">${escapeHtml(game.name)}</div>` +
            '<div class="game-card-meta">' +
                `<span class="${statusClass}">${gameStatus.toUpperCase()}</span>` +
                ` &middot; ${playerCount}/${game.max_players || '?'} players` +
                (game.current_round ? ` &middot; Round ${game.current_round}` : '') +
            '</div>' +
        '</div>' +
        '<div class="game-card-actions"></div>';

    const actionsEl = card.querySelector('.game-card-actions');

    if (gameStatus === 'lobby') {
        // Select species button (if player is already in the game)
        const myPlayer = (game.players || []).find(function (p) {
            return state.currentUser && Number(p.user_id) === Number(state.currentUser.id);
        });
        if (!myPlayer) {
            const joinBtn = document.createElement('button');
            joinBtn.textContent = 'Join';
            joinBtn.addEventListener('click', function () { joinGame(game.id); });
            actionsEl.appendChild(joinBtn);
        }
        if (myPlayer && !myPlayer.species) {
            const speciesBtn = document.createElement('button');
            speciesBtn.textContent = 'Pick Species';
            speciesBtn.className = 'btn-secondary';
            speciesBtn.addEventListener('click', function () { openSpeciesPicker(game.id); });
            actionsEl.appendChild(speciesBtn);
        }
        // Start game button for host (first player)
        if (myPlayer && Number(game.host_user_id) === Number(state.currentUser?.id)) {
            const startBtn = document.createElement('button');
            startBtn.textContent = 'Start';
            startBtn.addEventListener('click', function () { startGame(game.id); });
            actionsEl.appendChild(startBtn);
        }
        // Invite button only for joined players
        if (myPlayer) {
            const inviteBtn = document.createElement('button');
            inviteBtn.textContent = 'Invite';
            inviteBtn.className = 'btn-secondary';
            inviteBtn.addEventListener('click', function () { openInviteModal(game.id); });
            actionsEl.appendChild(inviteBtn);
        }
    }

    // Open game button for active/finished games
    if (gameStatus !== 'lobby') {
        const openBtn = document.createElement('button');
        openBtn.textContent = game.status === 'finished' ? 'View' : 'Play';
        openBtn.addEventListener('click', function () { openGame(game.id); });
        actionsEl.appendChild(openBtn);
    } else {
        const viewBtn = document.createElement('button');
        viewBtn.textContent = 'View';
        viewBtn.addEventListener('click', function () { openGame(game.id); });
        actionsEl.appendChild(viewBtn);
    }

    return card;
}

// ---------------------------------------------------------------------------
// Lobby: create game
// ---------------------------------------------------------------------------
document.getElementById('create-game-btn')?.addEventListener('click', function () {
    document.getElementById('create-game-modal')?.classList.remove('hidden');
    document.getElementById('game-name')?.focus();
});

document.getElementById('cancel-create-game')?.addEventListener('click', function () {
    document.getElementById('create-game-modal')?.classList.add('hidden');
    clearFormError('create-game-error');
});

document.getElementById('create-game-form')?.addEventListener('submit', async function (e) {
    e.preventDefault();
    clearFormError('create-game-error');

    const name = document.getElementById('game-name')?.value.trim();
    const maxPlayers = parseInt(document.getElementById('game-max-players')?.value, 10);

    // Client-side validation
    if (typeof Actions !== 'undefined') {
        const result = Actions.validateCreateGame(name, maxPlayers);
        if (!result.valid) {
            showFormError('create-game-error', result.errors.join(' '));
            return;
        }
    }

    try {
        await apiFetch('/games', {
            method: 'POST',
            body: JSON.stringify({ name, max_players: maxPlayers }),
        });
        document.getElementById('create-game-modal')?.classList.add('hidden');
        document.getElementById('create-game-form')?.reset();
        await loadLobby();
    } catch (err) {
        showFormError('create-game-error', `Failed to create game: ${err.message}`);
    }
});

// ---------------------------------------------------------------------------
// Lobby: species picker
// ---------------------------------------------------------------------------
const SPECIES_LIST = [
    { id: 'human', name: 'Human', desc: 'Balanced all-rounder with strong economy.' },
    { id: 'random', name: 'Random', desc: 'Let fate decide: assigns one random species at selection time.' },
    { id: 'eridani_empire', name: 'Eridani Empire', desc: 'Rich starting resources, fewer influence discs.' },
    { id: 'hydran_progress', name: 'Hydran Progress', desc: 'Bonus science income for fast research.' },
    { id: 'planta', name: 'Planta', desc: 'Unique hex shape and plant-like growth.' },
    { id: 'descendants_of_draco', name: 'Descendants of Draco', desc: 'Powerful ancient-tech starting ships.' },
    { id: 'mechanema', name: 'Mechanema', desc: 'Cheap upgrades and advanced ship builds.' },
    { id: 'orion_hegemony', name: 'Orion Hegemony', desc: 'Strong military with orbital capacity.' },
    { id: 'exiles', name: 'Exiles', desc: 'Mobile homeworld, starting on a starbase.' },
    { id: 'terran_directorate', name: 'Terran Directorate', desc: 'Economic powerhouse with trade bonuses.' },
];

const PICKABLE_SPECIES_IDS = SPECIES_LIST.filter(function (sp) { return sp.id !== 'random'; }).map(function (sp) { return sp.id; });
let _speciesTargetGameId = null;
let _selectedSpeciesId = null;

function setSelectedSpecies(speciesId) {
    _selectedSpeciesId = speciesId || null;
    const listEl = document.getElementById('species-list');
    listEl?.querySelectorAll('.species-card').forEach(function (card) {
        card.classList.toggle('selected', card.dataset.species === _selectedSpeciesId);
    });
    const confirmBtn = document.getElementById('confirm-species');
    if (confirmBtn) confirmBtn.disabled = !_selectedSpeciesId;
}

function resolveSpeciesSelection(speciesId) {
    if (speciesId !== 'random') return speciesId;
    if (PICKABLE_SPECIES_IDS.length === 0) return null;
    return PICKABLE_SPECIES_IDS[Math.floor(Math.random() * PICKABLE_SPECIES_IDS.length)];
}

function openSpeciesPicker(gameId) {
    _speciesTargetGameId = gameId;
    setSelectedSpecies(null);
    const listEl = document.getElementById('species-list');
    if (!listEl) return;

    listEl.innerHTML = SPECIES_LIST.map(function (sp) {
        return '<button type="button" class="species-card" data-species="' + sp.id + '">' +
            '<div class="species-card-name">' + escapeHtml(sp.name) + '</div>' +
            '<div class="species-card-desc">' + escapeHtml(sp.desc) + '</div>' +
            '</button>';
    }).join('');

    listEl.querySelectorAll('.species-card').forEach(function (card) {
        card.addEventListener('click', function () {
            setSelectedSpecies(card.dataset.species);
        });
    });

    document.getElementById('species-modal')?.classList.remove('hidden');
}

async function confirmSpeciesSelection(species) {
    if (!_speciesTargetGameId || !species) return;
    try {
        await apiFetch(`/games/${_speciesTargetGameId}/select-species`, {
            method: 'POST',
            body: JSON.stringify({ species }),
        });
        document.getElementById('species-modal')?.classList.add('hidden');
        _speciesTargetGameId = null;
        setSelectedSpecies(null);
        await loadLobby();
    } catch (err) {
        alert(`Failed to select species: ${err.message}`);
    }
}

document.getElementById('cancel-species')?.addEventListener('click', function () {
    document.getElementById('species-modal')?.classList.add('hidden');
    _speciesTargetGameId = null;
    setSelectedSpecies(null);
});

document.getElementById('confirm-species')?.addEventListener('click', async function () {
    const resolvedSpecies = resolveSpeciesSelection(_selectedSpeciesId);
    await confirmSpeciesSelection(resolvedSpecies);
});

// Close species modal when clicking outside the dialog
document.getElementById('species-modal')?.addEventListener('click', function (e) {
    if (e.target.id === 'species-modal') {
        document.getElementById('species-modal').classList.add('hidden');
        _speciesTargetGameId = null;
        setSelectedSpecies(null);
    }
});

// ---------------------------------------------------------------------------
// Lobby: invite player
// ---------------------------------------------------------------------------
let _inviteTargetGameId = null;

function openInviteModal(gameId) {
    _inviteTargetGameId = gameId;
    document.getElementById('invite-modal')?.classList.remove('hidden');
    document.getElementById('invite-email')?.focus();
}

document.getElementById('cancel-invite')?.addEventListener('click', function () {
    document.getElementById('invite-modal')?.classList.add('hidden');
    _inviteTargetGameId = null;
    clearFormError('invite-error');
});

document.getElementById('invite-form')?.addEventListener('submit', async function (e) {
    e.preventDefault();
    clearFormError('invite-error');
    if (!_inviteTargetGameId) return;

    const email = document.getElementById('invite-email')?.value.trim();
    if (!email) {
        showFormError('invite-error', 'Email is required.');
        return;
    }

    try {
        await apiFetch(`/games/${_inviteTargetGameId}/invite`, {
            method: 'POST',
            body: JSON.stringify({ email }),
        });
        document.getElementById('invite-modal')?.classList.add('hidden');
        document.getElementById('invite-form')?.reset();
        _inviteTargetGameId = null;
        alert('Invite sent!');
    } catch (err) {
        showFormError('invite-error', `Failed to send invite: ${err.message}`);
    }
});

// ---------------------------------------------------------------------------
// Lobby: join game
// ---------------------------------------------------------------------------
async function joinGame(gameId) {
    try {
        await apiFetch(`/games/${gameId}/join`, {
            method: 'POST',
            body: JSON.stringify({}),
        });
        await loadLobby();
    } catch (err) {
        alert(`Failed to join game: ${err.message}`);
    }
}

// ---------------------------------------------------------------------------
// Lobby: start game
// ---------------------------------------------------------------------------
async function startGame(gameId) {
    try {
        await apiFetch(`/games/${gameId}/start`, { method: 'POST' });
        await openGame(gameId);
    } catch (err) {
        alert(`Failed to start game: ${err.message}`);
    }
}

// ---------------------------------------------------------------------------
// Game view: open and render
// ---------------------------------------------------------------------------
async function openGame(gameId) {
    try {
        const gameData = await apiFetch(`/games/${gameId}`);
        state.currentGame = gameData;

        // Determine current player (the player record for the logged-in user)
        const myPlayer = (gameData.players || []).find(function (p) {
            return state.currentUser && p.user_id === state.currentUser.id;
        });
        state.currentPlayerId = myPlayer ? myPlayer.id : null;

        showSection('game-section');
        updateNavStatus(`${gameData.name} | Round ${gameData.current_round || '—'}`);

        // Initialize board once
        if (!state.boardInitialized && typeof Board !== 'undefined') {
            const svg = document.getElementById('game-board');
            if (svg) {
                Board.init(svg);
                Board.setTileClickHandler(function (tile, actionType) {
                    if (typeof Actions !== 'undefined') {
                        Actions.handleTileClick(tile, actionType || Actions.getSelectedAction());
                    }
                });
                state.boardInitialized = true;
            }
        }

        // Load board map
        if (typeof Board !== 'undefined' && gameData.status !== 'lobby') {
            await Board.loadMap(gameId, gameData.players || []);
        }

        // Turn banner
        if (typeof Actions !== 'undefined') {
            const isMyTurn = myPlayer ? myPlayer.is_active_turn : false;
            if (gameData.active_player_id) {
                const activePl = (gameData.players || []).find(function (p) {
                    return p.id === gameData.active_player_id;
                });
                const name = activePl ? (activePl.username || 'Unknown') : 'Unknown';
                Actions.showTurnBanner(
                    isMyTurn ? 'Your turn!' : `${name}'s turn`,
                    isMyTurn
                );
            }
        }

        // Action tiles
        const isMyTurn = myPlayer ? myPlayer.is_active_turn : false;
        if (typeof Actions !== 'undefined') {
            Actions.renderActionTiles(isMyTurn);
        }

        // Wire up action submit handler
        if (typeof Actions !== 'undefined') {
            Actions.setActionSubmitHandler(async function (actionType, payload) {
                await submitAction(gameId, actionType, payload);
            });
        }

        // Side panels
        if (typeof Panels !== 'undefined') {
            await Panels.refresh(gameId, state.currentPlayerId, gameData);
        }

    } catch (err) {
        alert(`Failed to open game: ${err.message}`);
    }
}

// ---------------------------------------------------------------------------
// Game: submit action
// ---------------------------------------------------------------------------
async function submitAction(gameId, actionType, payload) {
    try {
        await apiFetch(`/games/${gameId}/action`, {
            method: 'POST',
            body: JSON.stringify({ action_type: actionType, payload: payload || {} }),
        });
        // Refresh game state after action
        await openGame(gameId);
    } catch (err) {
        alert(`Action failed: ${err.message}`);
    }
}

// ---------------------------------------------------------------------------
// Board controls
// ---------------------------------------------------------------------------
document.getElementById('board-zoom-in')?.addEventListener('click', function () {
    if (typeof Board !== 'undefined' && Board._state) {
        Board._state.zoom = Math.min(4, Board._state.zoom * 1.2);
        if (typeof Board.render === 'function') Board.render();
    }
});

document.getElementById('board-zoom-out')?.addEventListener('click', function () {
    if (typeof Board !== 'undefined' && Board._state) {
        Board._state.zoom = Math.max(0.2, Board._state.zoom / 1.2);
        if (typeof Board.render === 'function') Board.render();
    }
});

document.getElementById('board-center')?.addEventListener('click', function () {
    if (typeof Board !== 'undefined' && typeof Board.centerView === 'function') {
        Board.centerView();
    }
});

// ---------------------------------------------------------------------------
// Back to lobby button
// ---------------------------------------------------------------------------
document.getElementById('back-to-lobby-btn')?.addEventListener('click', async function () {
    state.currentGame = null;
    state.currentPlayerId = null;
    await loadLobby();
    showSection('lobby-section');
});

// ---------------------------------------------------------------------------
// Expose for global use (invite links, tests)
// ---------------------------------------------------------------------------
window.openGame = openGame;

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
// Start the app
// ---------------------------------------------------------------------------
syncApiToken();
init();
