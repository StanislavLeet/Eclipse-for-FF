// Eclipse: Second Dawn - API Client Module
// Provides typed fetch wrappers for all game API endpoints.

const EclipseAPI = (() => {
    let _token = null;

    function setToken(token) {
        _token = token;
    }

    function getToken() {
        return _token;
    }

    async function request(path, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...(_token ? { Authorization: `Bearer ${_token}` } : {}),
            ...options.headers,
        };

        const response = await fetch(path, { ...options, headers });

        if (!response.ok) {
            let detail = `HTTP ${response.status}`;
            try {
                const body = await response.json();
                detail = body.detail || detail;
            } catch (_) {}
            const err = new Error(detail);
            err.status = response.status;
            throw err;
        }

        return response.json();
    }

    // Auth endpoints
    async function register(email, username, password) {
        return request('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ email, username, password }),
        });
    }

    async function login(email, password) {
        return request('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
        });
    }

    async function getMe() {
        return request('/auth/me');
    }

    async function logout() {
        return request('/auth/logout', { method: 'POST' });
    }

    // Game endpoints
    async function createGame(name, maxPlayers) {
        return request('/games', {
            method: 'POST',
            body: JSON.stringify({ name, max_players: maxPlayers }),
        });
    }

    async function getGame(gameId) {
        return request(`/games/${gameId}`);
    }

    async function listGames() {
        return request('/games');
    }

    async function selectSpecies(gameId, species) {
        return request(`/games/${gameId}/select-species`, {
            method: 'POST',
            body: JSON.stringify({ species }),
        });
    }

    async function startGame(gameId) {
        return request(`/games/${gameId}/start`, { method: 'POST' });
    }

    // Map endpoint
    async function getMap(gameId) {
        return request(`/games/${gameId}/map`);
    }

    // Status/scores
    async function getStatus(gameId) {
        return request(`/games/${gameId}/status`);
    }

    async function getScores(gameId) {
        return request(`/games/${gameId}/scores`);
    }

    // Player resources/tech/ships
    async function getResources(gameId, playerId) {
        return request(`/games/${gameId}/players/${playerId}/resources`);
    }

    async function getTechnologies(gameId, playerId) {
        return request(`/games/${gameId}/players/${playerId}/technologies`);
    }

    // Actions
    async function submitAction(gameId, actionType, payload) {
        return request(`/games/${gameId}/action`, {
            method: 'POST',
            body: JSON.stringify({ action_type: actionType, payload }),
        });
    }

    async function getActions(gameId) {
        return request(`/games/${gameId}/actions`);
    }

    // Health
    async function health() {
        return request('/health');
    }

    return {
        setToken,
        getToken,
        request,
        register,
        login,
        getMe,
        logout,
        createGame,
        getGame,
        listGames,
        selectSpecies,
        startGame,
        getMap,
        getStatus,
        getScores,
        getResources,
        getTechnologies,
        submitAction,
        getActions,
        health,
    };
})();

// Export for Node.js test environments (no-op in browser)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EclipseAPI;
}
