/* ═══════════════════════════════════════════════════════════════
   Q-ARunner — queue.js  (v4 — 16-module scheme aligned with UI)

   Canonical module layout (matches HTML execTogMod + app.js MOD_CB):
     grp 0 (Q Audit)    : idx 0–5
     grp 1 (Audit Plan) : idx 6–12
     grp 2 (Inventory)  : idx 13–15
═══════════════════════════════════════════════════════════════ */
'use strict';

if (window.__QA_QUEUE_LOADED__) {
  console.warn('[QA] queue.js already loaded — skipping duplicate.');
} else {
  /* 🛡️ Duplicate Protection (Step 2 Exec Architecture) */
  window.__QA_QUEUE_LOADED__ = true;

  /* ════════════════════════════════════
     MODULE CATALOGUE (Populated by app.js from /api/modules)
     idx  matches modEnabled[] and the ep{n} page ids in index.html
     grp  0=Q Audit  1=Audit Plan  2=Inventory
  ════════════════════════════════════ */
  // Use a getter to ensure we always have the latest from window.QA_MODULES
  const getCatalogue = () => window.QA_MODULES || [];

  /* Drag-priority order — tracks catalogue positions (not idx values) */
  let _queueOrder = null;
  let _sortable = null;

  function _getQueueOrder() {
    if (_queueOrder && _queueOrder.length === getCatalogue().length) return _queueOrder;
    _queueOrder = getCatalogue().map((_, i) => i);
    return _queueOrder;
  }

  /* ════════════════════════════════════
     STATE NORMALIZATION
     Ensures window.modEnabled is always length MODULE_COUNT.
     Protects against legacy 7-slot initializers and partial
     restores from older serialized configs.
  ════════════════════════════════════ */
  const MODULE_COUNT = 16;

  function _normalizeEnabled() {
    const me = window.modEnabled;
    if (!Array.isArray(me) || me.length < MODULE_COUNT) {
      const fixed = new Array(MODULE_COUNT).fill(false);
      if (Array.isArray(me)) me.forEach((v, i) => { if (i < MODULE_COUNT) fixed[i] = !!v; });
      window.modEnabled = fixed;
    }
  }

  /* ════════════════════════════════════
     ENABLED CHECK
  ════════════════════════════════════ */
  function _isEnabled(mod) {
    _normalizeEnabled();
    const ge = window.grpEnabled || [];
    const me = window.modEnabled;

    if (mod.idx >= me.length) {
      console.warn('[QA] modEnabled too short for idx', mod.idx, 'len', me.length);
      return false;
    }
    return !!(ge[mod.grp] && me[mod.idx]);
  }

  /* ════════════════════════════════════
     RENDER
  ════════════════════════════════════ */
  function _renderQueue() {
    const list = document.getElementById('run-queue-list');
    const empty = document.getElementById('rqempty-all');
    if (!list) return;

    const catalog = getCatalogue();
    if (!catalog.length) return;

    const order = _getQueueOrder();
    const enabled = order
      .map(i => catalog[i])
      .filter(_isEnabled);

    if (empty) empty.style.display = enabled.length ? 'none' : '';

    Array.from(list.children).forEach(el => {
      if (el.id !== 'rqempty-all') el.remove();
    });

    enabled.forEach((mod, priority) => {
      const item = document.createElement('div');
      item.className = `q-item q-active`;
      item.dataset.modIdx = mod.idx;

      item.innerHTML = `
      <span class="q-drag-handle" title="Drag to reorder">⠿</span>
      <span class="q-priority">${priority + 1}</span>
      <div class="q-item-body">
        <span class="q-icon">${mod.icon}</span>
        <span class="q-name">${mod.display}</span>
      </div>
      <span class="q-chip">Will Run</span>
    `;

      list.insertBefore(item, empty);
    });
  }

  /* ════════════════════════════════════
     PRIORITY POP ANIMATION
  ════════════════════════════════════ */
  function _animatePriorities() {
    document.querySelectorAll('#run-queue-list .q-priority').forEach((el, i) => {
      el.textContent = i + 1;
      el.classList.remove('pop');
      void el.offsetWidth;
      el.classList.add('pop');
    });
  }

  /* ════════════════════════════════════
     SORTABLE INIT
  ════════════════════════════════════ */
  function _initSortable() {
    const list = document.getElementById('run-queue-list');
    if (!list) return;

    if (typeof Sortable === 'undefined') {
      console.warn('[QA] queue.js: SortableJS not loaded — drag reorder disabled.');
      return;
    }

    if (_sortable) {
      try { _sortable.destroy(); } catch (_) { }
      _sortable = null;
    }

    _sortable = Sortable.create(list, {
      handle: '.q-drag-handle',
      animation: 200,
      easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      ghostClass: 'sortable-ghost',
      chosenClass: 'sortable-chosen',
      dragClass: 'sortable-drag',
      filter: '#rqempty-all',
      onMove(evt) {
        return evt.related.id !== 'rqempty-all';
      },
      onEnd(evt) {
        const newOrder = [];
        const catalog = getCatalogue();
        list.querySelectorAll('.q-item[data-mod-idx]').forEach(el => {
          const domModIdx = parseInt(el.dataset.modIdx, 10);
          const catalogIdx = catalog.findIndex(m => m.idx === domModIdx);
          if (catalogIdx >= 0) newOrder.push(catalogIdx);
        });

        _queueOrder.forEach(i => {
          if (!newOrder.includes(i)) newOrder.push(i);
        });

        _queueOrder = newOrder;
        _animatePriorities();
      },
    });
  }

  /* ════════════════════════════════════
     SIDEBAR STATE SYNC
  ════════════════════════════════════ */
  function syncSidebarState() {
    const ge = window.grpEnabled || [];
    const catalog = getCatalogue();

    window.QA_MODULES.forEach(mod => {
      const entryId = 'emr-' + mod.idx;
      const enabled = _isEnabled(mod);

      const el = document.getElementById(entryId);
      if (!el) return;

      const wasEnabled = el.classList.contains('mod-enabled');
      el.classList.toggle('mod-enabled', enabled);
      el.classList.toggle('mod-disabled', !enabled);

      if (enabled && !wasEnabled) {
        el.classList.remove('just-enabled');
        void el.offsetWidth;
        el.classList.add('just-enabled');
        setTimeout(() => el.classList.remove('just-enabled'), 500);
      }
    });

    [0, 1, 2].forEach(grpIdx => {
      const hd = document.getElementById('sbh-' + grpIdx);
      if (!hd) return;
      const on = !!(ge[grpIdx]);
      hd.classList.toggle('grp-enabled', on);
      hd.classList.toggle('grp-disabled', !on);
    });
  }

  window.syncSidebarState = syncSidebarState;

  /* ════════════════════════════════════
     PUBLIC API
  ════════════════════════════════════ */

  window.syncRunQueue = function syncRunQueue() {
    _renderQueue();
    _initSortable();
    syncSidebarState();
  };

  /**
   * getQueueOrder()
   * Returns enabled module .idx values in current drag priority order.
   * Used by config.js → buildCfg() → MODULE_RUN_ORDER.
   * 
   * 🔀 Step 2 Execution Architecture (Execution Order Controller)
   * Resolves the fixed index mapping into the final run order array.
   */
  window.getQueueOrder = function getQueueOrder() {
    const catalog = getCatalogue();
    return _getQueueOrder()
      .map(i => catalog[i])
      .filter(_isEnabled)
      .map(m => m.idx);
  };

  /* ════════════════════════════════════
     INIT
  ════════════════════════════════════ */
  document.addEventListener('DOMContentLoaded', () => {
    requestAnimationFrame(() => {
      _renderQueue();
      _initSortable();
      syncSidebarState();
    });
  });

  /* ════════════════════════════════════
     TOGGLE SWITCH — sidebar mini toggles
  ════════════════════════════════════ */

  function _setToggleState(toggleEl, state, animate) {
    if (!toggleEl) return;
    toggleEl.dataset.state = state;
    toggleEl.setAttribute('aria-checked', state === 'enabled' ? 'true' : 'false');
    if (animate) {
      toggleEl.classList.remove('just-toggled');
      void toggleEl.offsetWidth;
      toggleEl.classList.add('just-toggled');
      setTimeout(() => toggleEl.classList.remove('just-toggled'), 500);
    }
  }

  function _syncToggleFromMod(modIdx) {
    const toggleEl = document.querySelector(`.toggle-switch[data-mod="${modIdx}"]`);
    if (!toggleEl) return;
    const enabled = !!(window.modEnabled && window.modEnabled[modIdx]);
    _setToggleState(toggleEl, enabled ? 'enabled' : 'disabled', false);
  }

  function _handleToggleClick(e) {
    e.stopPropagation();

    const toggleEl = e.currentTarget;
    const modIdx = parseInt(toggleEl.dataset.mod, 10);
    const cbId = toggleEl.dataset.cb;
    if (isNaN(modIdx) || !cbId) return;

    const cb = document.getElementById(cbId);
    if (!cb) return;
    cb.checked = !cb.checked;

    if (typeof window.execTogMod === 'function') {
      window.execTogMod(modIdx);
    }

    _setToggleState(toggleEl, cb.checked ? 'enabled' : 'disabled', true);
  }

  function _handleToggleKey(e) {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      _handleToggleClick(e);
    }
  }

  function initToggleSwitches() {
    document.querySelectorAll('.toggle-switch[data-mod]').forEach(toggleEl => {
      if (toggleEl.dataset.tsInit) return;
      toggleEl.dataset.tsInit = '1';
      toggleEl.addEventListener('click', _handleToggleClick);
      toggleEl.addEventListener('keydown', _handleToggleKey);
    });
  }

  function syncAllToggles() {
    document.querySelectorAll('.toggle-switch[data-mod]').forEach(toggleEl => {
      const modIdx = parseInt(toggleEl.dataset.mod, 10);
      _syncToggleFromMod(modIdx);
    });
  }

  window.syncAllToggles = syncAllToggles;
  window._syncToggleFromMod = _syncToggleFromMod;

  /* Patch syncSidebarState to also refresh toggle visuals */
  const _origSyncSidebarState = window.syncSidebarState;
  window.syncSidebarState = function () {
    if (typeof _origSyncSidebarState === 'function') _origSyncSidebarState();
    syncAllToggles();
  };

  document.addEventListener('DOMContentLoaded', () => {
    requestAnimationFrame(() => {
      initToggleSwitches();
      syncAllToggles();
    });
  });

  console.info('[QA] queue.js v3 loaded ✓');
} // end duplicate-load guard
