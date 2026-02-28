// Eclipse: Second Dawn - Actions Module
// Manages action tile UI, confirmation dialogs, combat log, and turn notifications.

const Actions = (() => {
    // All player action types in activation phase order.
    const ACTION_TYPES = ['EXPLORE', 'INFLUENCE', 'BUILD', 'RESEARCH', 'MOVE', 'UPGRADE', 'PASS'];

    // Short descriptions shown as tooltips on action tiles.
    const ACTION_DESCRIPTIONS = {
        EXPLORE: 'Move a ship into an unexplored hex to reveal it',
        INFLUENCE: 'Claim a system by placing an influence disc',
        BUILD: 'Spend materials to construct new ships or structures',
        RESEARCH: 'Spend science to acquire a new technology',
        MOVE: 'Move ships through wormhole-connected hexes',
        UPGRADE: 'Modify a ship blueprint with new components',
        PASS: 'End your activation-phase turns for this round',
    };

    let _selectedAction = null;
    let _onActionSubmit = null;

    // ---------------------------------------------------------------------------
    // Action tiles panel
    // ---------------------------------------------------------------------------

    function renderActionTiles(isMyTurn) {
        const el = document.getElementById('action-tiles');
        if (!el) return;

        if (!isMyTurn) {
            el.innerHTML = '<p class="panel-empty">Waiting for other players...</p>';
            return;
        }

        const tiles = ACTION_TYPES.map(function (action) {
            const selected = _selectedAction === action ? ' selected' : '';
            const desc = ACTION_DESCRIPTIONS[action] || '';
            return '<button class="action-tile' + selected + '" data-action="' + action + '" title="' + desc + '">' +
                action +
                '</button>';
        }).join('');

        el.innerHTML = '<h3>Actions</h3><div class="action-tiles-grid">' + tiles + '</div>';

        el.querySelectorAll('.action-tile').forEach(function (btn) {
            btn.addEventListener('click', function () { selectAction(btn.dataset.action); });
        });
    }

    function selectAction(actionType) {
        _selectedAction = actionType;

        // Refresh visual state
        document.querySelectorAll('.action-tile').forEach(function (btn) {
            btn.classList.toggle('selected', btn.dataset.action === actionType);
        });

        // Notify board
        if (typeof Board !== 'undefined') {
            if (actionType === 'PASS') {
                Board.clearHighlights();
                showConfirmDialog('PASS', {}, 'Confirm Pass', 'End your turns for this round?', null);
            } else {
                // Clear previous highlights; real path highlighting would come from a server query.
                Board.setHighlightedTiles(actionType, []);
            }
        }
    }

    function getSelectedAction() {
        return _selectedAction;
    }

    function clearSelection() {
        _selectedAction = null;
        document.querySelectorAll('.action-tile').forEach(function (btn) {
            btn.classList.remove('selected');
        });
        if (typeof Board !== 'undefined') Board.clearHighlights();
    }

    // ---------------------------------------------------------------------------
    // Confirmation dialogs
    // ---------------------------------------------------------------------------

    function _getOrCreateDialog() {
        let dialog = document.getElementById('action-dialog');
        if (!dialog) {
            dialog = document.createElement('div');
            dialog.id = 'action-dialog';
            dialog.className = 'dialog-overlay hidden';
            document.body.appendChild(dialog);
        }
        return dialog;
    }

    /**
     * Show a confirmation dialog for an action.
     * @param {string} actionType - e.g. 'BUILD'
     * @param {Object} payload    - base payload to merge with dialog fields
     * @param {string} title
     * @param {string} message
     * @param {string|null} extraHtml - optional extra form HTML injected into dialog
     */
    function showConfirmDialog(actionType, payload, title, message, extraHtml) {
        const dialog = _getOrCreateDialog();

        dialog.innerHTML =
            '<div class="dialog-box">' +
                '<h3 class="dialog-title">' + escapeHtml(title) + '</h3>' +
                '<p class="dialog-message">' + escapeHtml(message) + '</p>' +
                (extraHtml || '') +
                '<div class="dialog-buttons">' +
                    '<button id="dialog-confirm" class="btn-confirm">Confirm</button>' +
                    '<button id="dialog-cancel" class="btn-cancel">Cancel</button>' +
                '</div>' +
            '</div>';

        dialog.classList.remove('hidden');

        document.getElementById('dialog-confirm').addEventListener('click', function () {
            const extra = _collectDialogData(dialog);
            closeDialog();
            if (_onActionSubmit) {
                const merged = {};
                Object.assign(merged, payload, extra);
                _onActionSubmit(actionType, merged);
            }
        });

        document.getElementById('dialog-cancel').addEventListener('click', function () {
            closeDialog();
            clearSelection();
        });
    }

    function _collectDialogData(dialog) {
        const result = {};
        dialog.querySelectorAll('[data-field]').forEach(function (el) {
            result[el.dataset.field] = el.value !== undefined ? el.value : el.dataset.value;
        });
        return result;
    }

    function closeDialog() {
        const dialog = document.getElementById('action-dialog');
        if (dialog) dialog.classList.add('hidden');
        clearSelection();
    }

    // BUILD dialog: choose ship type
    function showBuildDialog() {
        const extra =
            '<div class="dialog-field">' +
                '<label for="build-ship-type">Ship Type</label>' +
                '<select id="build-ship-type" data-field="ship_type">' +
                    '<option value="interceptor">Interceptor (2 materials)</option>' +
                    '<option value="cruiser">Cruiser (3 materials)</option>' +
                    '<option value="dreadnought">Dreadnought (5 materials)</option>' +
                    '<option value="starbase">Starbase (3 materials)</option>' +
                '</select>' +
            '</div>';
        showConfirmDialog('BUILD', {}, 'Build Ship', 'Choose a ship type to construct:', extra);
    }

    // RESEARCH dialog: choose from available technologies
    function showResearchDialog(techs) {
        let extra;
        if (techs && techs.length > 0) {
            const options = techs.map(function (t) {
                const id = escapeHtml(String(t.id || t.tech_id || ''));
                const name = escapeHtml(t.name || id);
                const cost = t.cost || '?';
                return '<option value="' + id + '">' + name + ' (' + cost + ' sci)</option>';
            }).join('');
            extra =
                '<div class="dialog-field">' +
                    '<label for="research-tech">Technology</label>' +
                    '<select id="research-tech" data-field="tech_id">' + options + '</select>' +
                '</div>';
        } else {
            extra = '<p class="panel-error">No technologies available to research</p>';
        }
        showConfirmDialog('RESEARCH', {}, 'Research Technology', 'Choose a technology to acquire:', extra);
    }

    // UPGRADE dialog: choose ship type and component slot/id
    function showUpgradeDialog() {
        const extra =
            '<div class="dialog-field">' +
                '<label for="upgrade-ship-type">Ship Type</label>' +
                '<select id="upgrade-ship-type" data-field="ship_type">' +
                    '<option value="interceptor">Interceptor</option>' +
                    '<option value="cruiser">Cruiser</option>' +
                    '<option value="dreadnought">Dreadnought</option>' +
                    '<option value="starbase">Starbase</option>' +
                '</select>' +
            '</div>' +
            '<div class="dialog-field">' +
                '<label for="upgrade-slot">Slot</label>' +
                '<input type="number" id="upgrade-slot" data-field="slot" min="0" max="5" value="0">' +
            '</div>' +
            '<div class="dialog-field">' +
                '<label for="upgrade-component">Component ID</label>' +
                '<input type="text" id="upgrade-component" data-field="component_id" placeholder="e.g. ion_cannon">' +
            '</div>';
        showConfirmDialog('UPGRADE', {}, 'Upgrade Blueprint', 'Modify a ship blueprint component:', extra);
    }

    // ---------------------------------------------------------------------------
    // Combat log panel
    // ---------------------------------------------------------------------------

    function renderCombatLog(logs) {
        const el = document.getElementById('combat-log');
        if (!el) return;

        if (!logs || logs.length === 0) {
            el.innerHTML = '<h3>Combat Log</h3><p class="panel-empty">No combat this round</p>';
            return;
        }

        const html = logs.map(function (log) {
            const entries = (log.log_entries || []).map(function (entry) {
                const text = typeof entry === 'string' ? entry : JSON.stringify(entry);
                return '<li class="combat-entry">' + escapeHtml(text) + '</li>';
            }).join('');

            return '<div class="combat-round">' +
                '<div class="combat-header">Round ' + (log.round_number || '?') +
                    ' &mdash; Hex ' + (log.hex_tile_id || '?') + '</div>' +
                '<ul class="combat-entries">' + entries + '</ul>' +
                '</div>';
        }).join('');

        el.innerHTML = '<h3>Combat Log</h3><div class="combat-log-list">' + html + '</div>';
    }

    // ---------------------------------------------------------------------------
    // Turn notification banner
    // ---------------------------------------------------------------------------

    function showTurnBanner(message, isMyTurn) {
        const el = document.getElementById('turn-banner');
        if (!el) return;
        el.textContent = message;
        el.className = 'turn-banner ' + (isMyTurn ? 'my-turn' : 'other-turn');
        el.classList.remove('hidden');
    }

    function hideTurnBanner() {
        const el = document.getElementById('turn-banner');
        if (el) el.classList.add('hidden');
    }

    // ---------------------------------------------------------------------------
    // Board tile click dispatcher
    // ---------------------------------------------------------------------------

    function handleTileClick(tile, actionType) {
        if (!actionType) return;

        switch (actionType) {
            case 'MOVE':
                showConfirmDialog('MOVE', { target_hex_id: tile.id },
                    'Move Ships',
                    'Move ships to (' + tile.q + ', ' + tile.r + ')?',
                    null);
                break;
            case 'EXPLORE':
                showConfirmDialog('EXPLORE', { hex_tile_id: tile.id },
                    'Explore Hex',
                    'Send ships to explore (' + tile.q + ', ' + tile.r + ')?',
                    null);
                break;
            case 'INFLUENCE':
                showConfirmDialog('INFLUENCE', { hex_tile_id: tile.id },
                    'Claim System',
                    'Claim system at (' + tile.q + ', ' + tile.r + ')?',
                    null);
                break;
            case 'BUILD':
                showBuildDialog();
                break;
            case 'RESEARCH':
                showResearchDialog([]);
                break;
            case 'UPGRADE':
                showUpgradeDialog();
                break;
            default:
                break;
        }
    }

    // ---------------------------------------------------------------------------
    // Event wiring
    // ---------------------------------------------------------------------------

    function setActionSubmitHandler(fn) {
        _onActionSubmit = fn;
    }

    // ---------------------------------------------------------------------------
    // Form validation helpers (used externally and in tests)
    // ---------------------------------------------------------------------------

    /**
     * Validate a create-game form payload.
     * Returns { valid: bool, errors: string[] }
     */
    function validateCreateGame(name, maxPlayers) {
        const errors = [];
        if (!name || name.trim().length === 0) {
            errors.push('Game name is required');
        }
        if (!name || name.trim().length > 80) {
            errors.push('Game name must be 80 characters or fewer');
        }
        const n = parseInt(maxPlayers, 10);
        if (isNaN(n) || n < 2 || n > 6) {
            errors.push('Max players must be between 2 and 6');
        }
        return { valid: errors.length === 0, errors: errors };
    }

    /**
     * Validate a register form payload.
     * Returns { valid: bool, errors: string[] }
     */
    function validateRegister(email, username, password) {
        const errors = [];
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!email || !emailRegex.test(email)) {
            errors.push('Valid email address is required');
        }
        if (!username || username.trim().length < 2) {
            errors.push('Username must be at least 2 characters');
        }
        if (!password || password.length < 6) {
            errors.push('Password must be at least 6 characters');
        }
        return { valid: errors.length === 0, errors: errors };
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
        ACTION_TYPES,
        ACTION_DESCRIPTIONS,
        renderActionTiles,
        selectAction,
        getSelectedAction,
        clearSelection,
        showConfirmDialog,
        showBuildDialog,
        showResearchDialog,
        showUpgradeDialog,
        closeDialog,
        renderCombatLog,
        showTurnBanner,
        hideTurnBanner,
        handleTileClick,
        setActionSubmitHandler,
        validateCreateGame,
        validateRegister,
        escapeHtml,
    };
})();

if (typeof module !== 'undefined' && module.exports) {
    module.exports = Actions;
}
