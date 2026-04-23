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
     MODULE CATALOGUE
     idx  matches modEnabled[] and the ep{n} page ids in index.html
     grp  0=Q Audit  1=Audit Plan  2=Inventory
  ════════════════════════════════════ */
  const QUEUE_MODULES = [
    { idx: 0,  name: 'Q_Setting', icon: '⚙️', cls: 'q-active', grp: 0 },
    { idx: 1,  name: 'Stock Audit A1', icon: '📦', cls: 'q-active', grp: 0 },
    { idx: 2,  name: 'Stock Audit A2', icon: '📦', cls: 'q-active', grp: 0 },
    { idx: 3,  name: 'Summary Table', icon: '📉', cls: 'q-active', grp: 0 },
    { idx: 4,  name: 'Recently Audited', icon: '🕐', cls: 'q-active', grp: 0 },
    { idx: 5,  name: 'Q_audit_Summary', icon: '📊', cls: 'q-active', grp: 0 },
    { idx: 6,  name: 'Audit Plan', icon: '📅', cls: 'q-active', grp: 1 },
    { idx: 7,  name: 'Ongoing Audit', icon: '🔄', cls: 'q-active', grp: 1 },
    { idx: 8,  name: 'Auditor 1 SA', icon: '👤', cls: 'q-active', grp: 1 },
    { idx: 9,  name: 'Auditor 2 SA', icon: '👤', cls: 'q-active', grp: 1 },
    { idx: 10, name: 'Auditor 2 Table', icon: '📉', cls: 'q-active', grp: 1 },
    { idx: 11, name: 'Auditor 2 Summary', icon: '📊', cls: 'q-active', grp: 1 },
    { idx: 12, name: 'Auditor 2 Recent', icon: '🕐', cls: 'q-active', grp: 1 },
    { idx: 13, name: 'Create Group', icon: '📁', cls: 'q-active', grp: 2 },
    { idx: 14, name: 'Location Setup', icon: '📍', cls: 'q-active', grp: 2 },
    { idx: 15, name: 'Import Items', icon: '📥', cls: 'q-active', grp: 2 }
  ];

  /* Drag-priority order — tracks catalogue positions (not idx values) */
  let _queueOrder = QUEUE_MODULES.map((_, i) => i);
  let _sortable = null;

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

    const enabled = _queueOrder
      .map(i => QUEUE_MODULES[i])
      .filter(_isEnabled);

    if (empty) empty.style.display = enabled.length ? 'none' : '';

    Array.from(list.children).forEach(el => {
      if (el.id !== 'rqempty-all') el.remove();
    });

    enabled.forEach((mod, priority) => {
      const item = document.createElement('div');
      item.className = `q-item ${mod.cls}`;
      item.dataset.modIdx = mod.idx;

      item.innerHTML = `
      <span class="q-drag-handle" title="Drag to reorder">⠿</span>
      <span class="q-priority">${priority + 1}</span>
      <div class="q-item-body">
        <span class="q-icon">${mod.icon}</span>
        <span class="q-name">${mod.name}</span>
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
        if (evt.oldIndex === evt.newIndex) return;

        const newOrder = [];
        list.querySelectorAll('.q-item[data-mod-idx]').forEach(el => {
          const domModIdx = parseInt(el.dataset.modIdx, 10);
          const catalogIdx = QUEUE_MODULES.findIndex(m => m.idx === domModIdx);
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
  const SB_SUB_MAP = [
    { id: 'emr-0', modIdx: 0, grp: 0 },
    { id: 'emr-1', modIdx: 1, grp: 0 },
    { id: 'emr-2', modIdx: 2, grp: 0 },
    { id: 'emr-3', modIdx: 3, grp: 0 },
    { id: 'emr-4', modIdx: 4, grp: 0 },
    { id: 'emr-5', modIdx: 5, grp: 0 },
    { id: 'emr-6', modIdx: 6, grp: 1 },
    { id: 'emr-7', modIdx: 7, grp: 1 },
    { id: 'emr-8', modIdx: 8, grp: 1 },
    { id: 'emr-9', modIdx: 9, grp: 1 },
    { id: 'emr-10', modIdx: 10, grp: 1 },
    { id: 'emr-11', modIdx: 11, grp: 1 },
    { id: 'emr-12', modIdx: 12, grp: 1 },
    { id: 'emr-13', modIdx: 13, grp: 2 },
    { id: 'emr-14', modIdx: 14, grp: 2 },
    { id: 'emr-15', modIdx: 15, grp: 2 },
  ];

  function syncSidebarState() {
    const ge = window.grpEnabled || [];

    SB_SUB_MAP.forEach(entry => {
      /* Find the catalogue entry for this sidebar row */
      const mod = QUEUE_MODULES.find(m => m.idx === entry.modIdx);
      const enabled = mod ? _isEnabled(mod) : false;

      const el = document.getElementById(entry.id);
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
    return _queueOrder
      .map(i => QUEUE_MODULES[i])
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
