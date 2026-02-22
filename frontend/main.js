// Eclipse: Second Dawn - Main Frontend Entry Point

const API_BASE = '';  // Same origin

// State
const state = {
    token: localStorage.getItem('eclipse_token'),
    currentUser: null,
    currentGame: null,
};

// Utility functions
async function apiFetch(path, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...(state.token ? { 'Authorization': `Bearer ${state.token}` } : {}),
        ...options.headers,
    };

    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
}

function showSection(id) {
    ['loading-screen', 'auth-section', 'lobby-section', 'game-section'].forEach(sid => {
        const el = document.getElementById(sid);
        if (el) el.classList.toggle('hidden', sid !== id);
    });
}

function updateNavStatus(text) {
    const el = document.getElementById('nav-status');
    if (el) el.textContent = text;
}

// Auth
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
        document.getElementById('loading-screen').textContent = 'Cannot connect to server.';
        return;
    }

    if (state.token) {
        try {
            state.currentUser = await apiFetch('/auth/me');
            updateNavStatus(`Logged in as ${state.currentUser.username}`);
            showSection('lobby-section');
        } catch {
            localStorage.removeItem('eclipse_token');
            state.token = null;
            showSection('auth-section');
        }
    } else {
        showSection('auth-section');
    }
}

// Login form
document.getElementById('login-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;

    try {
        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);

        const data = await apiFetch('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData,
        });

        state.token = data.access_token;
        localStorage.setItem('eclipse_token', state.token);
        await init();
    } catch (err) {
        alert(`Login failed: ${err.message}`);
    }
});

// Register form
document.getElementById('register-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('reg-email').value;
    const username = document.getElementById('reg-username').value;
    const password = document.getElementById('reg-password').value;

    try {
        await apiFetch('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ email, username, password }),
        });
        alert('Registration successful! Please login.');
        document.getElementById('register-panel').classList.add('hidden');
        document.getElementById('login-panel').classList.remove('hidden');
    } catch (err) {
        alert(`Registration failed: ${err.message}`);
    }
});

// Panel toggles
document.getElementById('show-register')?.addEventListener('click', (e) => {
    e.preventDefault();
    document.getElementById('login-panel').classList.add('hidden');
    document.getElementById('register-panel').classList.remove('hidden');
});

document.getElementById('show-login')?.addEventListener('click', (e) => {
    e.preventDefault();
    document.getElementById('register-panel').classList.add('hidden');
    document.getElementById('login-panel').classList.remove('hidden');
});

// Start app
init();
