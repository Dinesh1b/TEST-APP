/* ═══════════════════════════════════════════════════════════════
   Q-ARunner — app.js  (v11 — Ongoing Audit / Auditor 1 SA refactor)
   CHANGES v11:
     • Added validateOAMapping() for ep10 Field Mapping JSON textarea
     • No structural changes — UI refactor handled in index.html
═══════════════════════════════════════════════════════════════ */
'use strict';

if (window.__QA_APP_LOADED__) {
  console.warn('[QA] app.js already loaded — skipping.');
} else {
  /* 🎯 Step 1 Execution Architecture (UI + Config Builder) */
  window.__QA_APP_LOADED__ = true;

  /* ─────────────────────────────────────────────
     CONSTANTS
  ───────────────────────────────────────────── */
  const SETUP_STEPS = ['Environment', 'Login'];

  const MOD_NAMES = [
    'Q_Setting',            // 0
    'Stock Audit A1',       // 1
    'Stock Audit A2',       // 2
    'Summary Table',        // 3
    'Recently Audited',     // 4
    'Q_audit_Summary',      // 5
    'Audit_Plan',           // 6
    'Ongoing_Audit',        // 7
    'Auditor 1 SA',         // 8
    'Auditor 2 SA',         // 9
    'Table',                // 10
    'Summary',              // 11
    'Recent',               // 12
    'Create Group',         // 13
    'Location Setup',       // 14
    'Import Items',         // 15
  ];

  /*
    Flat lookup: module index → checkbox id
  */
  const MOD_CB = {
    0: 'cb-qs',
    1: 'cb-sa1',
    2: 'cb-sa2',
    3: 'cb-sum',
    4: 'cb-rec',
    5: 'cb-qsum',
    6: 'cb-ap',
    7: 'cb-oa',
    8: 'cb-asa',
    9: 'cb-asa2',
    10: 'cb-atab',
    11: 'cb-asum',
    12: 'cb-arec',
    13: 'cb-cg',
    14: 'cb-ls',
    15: 'cb-ii',
  };

  const MOD_TGL = {
    0: 'tgl-qs',
    1: 'tgl-sa1',
    2: 'tgl-sa2',
    3: 'tgl-sum',
    4: 'tgl-rec',
    5: 'tgl-qsum',
    6: 'tgl-ap',
    7: 'tgl-oa',
    8: 'tgl-asa',
    9: 'tgl-asa2',
    10: 'tgl-atab',
    11: 'tgl-asum',
    12: 'tgl-arec',
    13: 'tgl-cg',
    14: 'tgl-ls',
    15: 'tgl-ii',
  };

  const TOTAL_SUBS = 16;

  /* ─────────────────────────────────────────────
     SHARED STATE  (read by config.js / run.js)
  ───────────────────────────────────────────── */
  window.modEnabled = window.modEnabled || new Array(16).fill(false);
  window.grpEnabled = window.grpEnabled || [false, false, false];

  let _grpExpanded = [false, false, false];
  let _currentTab = 'setup';
  let _setupStep = 0;
  let _execModule = 1;
  let _execSelected = false;

  /* ─────────────────────────────────────────────
     SAFE DOM
  ───────────────────────────────────────────── */
  const $ = id => document.getElementById(id);

  /* ─────────────────────────────────────────────
     TAB SWITCHING
  ───────────────────────────────────────────── */
  window.switchTab = function switchTab(tab) {
    _currentTab = tab;

    ['setup', 'execution', 'run'].forEach(t =>
      $('tab-' + t)?.classList.toggle('active', t === tab)
    );
    ['sb-setup', 'sb-execution', 'sb-run'].forEach(id =>
      $(id)?.classList.remove('visible')
    );
    $('sb-' + tab)?.classList.add('visible');

    $('content-setup').style.display = 'none';
    $('content-execution').style.display = 'none';
    $('content-run').style.display = 'none';

    const sidebar = document.querySelector('.sidebar');
    if (sidebar) sidebar.style.display = tab === 'run' ? 'none' : '';

    if (tab === 'setup') {
      $('content-setup').style.display = 'block';
      _setCtx('Setup', SETUP_STEPS[_setupStep],
        `<button class="btn btn-ghost" onclick="switchTab('execution')">Execution →</button>`
      );
      goSetupStep(_setupStep, true);

    } else if (tab === 'execution') {
      $('content-execution').style.display = 'flex';
      _setCtx('Execution', _execSelected ? (MOD_NAMES[_execModule] || 'Module') : 'Select a module',
        `<button class="btn btn-ghost" onclick="switchTab('run')">Go to Run →</button>`
      );
      if (_execSelected) {
        goExecModule(_execModule, true);
      } else {
        document.querySelectorAll('#content-execution .page').forEach(p => p.classList.remove('active'));
        $('exec-empty-state').style.display = '';
        document.querySelectorAll('.sb-sub').forEach(r => r.classList.remove('active'));
      }
      setTimeout(() => window._updateScrollHint?.(), 50);

    } else {
      $('content-run').style.display = 'flex';
      _setCtx('Run', 'Launch & Monitor', '');
      syncRunQueue();
    }
  };

  function _setCtx(mode, step, actionsHtml) {
    const ml = $('ctx-mode-lbl'); if (ml) ml.textContent = mode;
    const sl = $('ctx-step-lbl'); if (sl) sl.textContent = step;
    const ac = $('ctx-actions'); if (ac) ac.innerHTML = actionsHtml;
  }

  /* ─────────────────────────────────────────────
     SETUP STEPS
  ───────────────────────────────────────────── */
  window.goSetupStep = function goSetupStep(n, silent) {
    _setupStep = n;
    if (!silent) {
      document.querySelectorAll('#content-setup .page').forEach((p, i) =>
        p.classList.toggle('active', i === n)
      );
    }
    document.querySelectorAll('#sb-setup .sb-item').forEach((el, i) =>
      el.classList.toggle('active', i === n)
    );
    _setCtx('Setup', SETUP_STEPS[n], $('ctx-actions')?.innerHTML || '');
    const pct = $('setup-pct'); if (pct) pct.textContent = (n + 1) + ' / 2';
    const fill = $('setup-fill'); if (fill) fill.style.width = ((n + 1) / 2 * 100) + '%';
    $('content-setup')?.scrollTo(0, 0);
  };

  /* ─────────────────────────────────────────────
     EXECUTION MODULE NAV
     Pages: ep0-ep8, ep10, ep11
     Note: there is no ep9 in the HTML — index 9 is unused.
  ───────────────────────────────────────────── */
  window.goExecModule = function goExecModule(n, silent) {
    _execModule = n;
    _execSelected = true;
    $('exec-empty-state').style.display = 'none';

    /* Toggle .active on all exec pages.
       Pages are identified by id="ep{n}" not by DOM order,
       so we can't use forEach with array index. */
    document.querySelectorAll('#content-execution .page').forEach(p => {
      p.classList.remove('active');
    });
    $('ep' + n)?.classList.add('active');

    document.querySelectorAll('.sb-sub').forEach(r => r.classList.remove('active'));

    const direct = $('emr-' + n);
    if (direct) direct.classList.add('active');

    _setCtx(
      _currentTab === 'execution' ? 'Execution' : _currentTab,
      MOD_NAMES[n] || ('Module ' + n),
      $('ctx-actions')?.innerHTML || ''
    );
    $('exec-content-scroll')?.scrollTo(0, 0);
  };

  /* Navigate from sidebar sub-row */
  window.navSub = function navSub(moduleIdx) {
    /* groupMap: which accordion group each module belongs to
       0: Q Audit (0-5)
       1: Audit Plan (6-13)
       2: Inventory (14-16)
    */
    const groupMap = {
      0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0,
      6: 1, 7: 1, 8: 1, 9: 1, 10: 1, 11: 1, 12: 1, 13: 1,
      14: 2, 15: 2, 16: 2
    };
    const grp = groupMap[moduleIdx] ?? 0;
    if (!_grpExpanded[grp]) {
      window.grpEnabled[grp] = true;
      _setGroupOpen(grp, true);
      const sw = $('grp-sw-' + grp); if (sw) sw.checked = true;
      syncRunQueue();
    }
    if (_currentTab !== 'execution') window.switchTab('execution');
    goExecModule(moduleIdx);
  };

  /* ─────────────────────────────────────────────
     GROUP ACCORDION
  ───────────────────────────────────────────── */
  window.togGroupSwitch = function togGroupSwitch(grpIdx) {
    const sw = $('grp-sw-' + grpIdx);
    window.grpEnabled[grpIdx] = sw?.checked ?? false;
    _setGroupOpen(grpIdx, window.grpEnabled[grpIdx]);
    syncModCount();
    syncRunQueue();
  };

  window.togGroupExpand = function togGroupExpand(grpIdx) {
    const newOpen = !_grpExpanded[grpIdx];
    _setGroupOpen(grpIdx, newOpen);
    window.grpEnabled[grpIdx] = newOpen;
    const sw = $('grp-sw-' + grpIdx); if (sw) sw.checked = newOpen;
    syncModCount();
    syncRunQueue();
    setTimeout(() => window._updateScrollHint?.(), 200);
  };

  function _setGroupOpen(grpIdx, open) {
    _grpExpanded[grpIdx] = open;
    $('sgbody-' + grpIdx)?.classList.toggle('open', open);
    $('sbh-' + grpIdx)?.classList.toggle('open', open);
    const chev = $('sgchev-' + grpIdx);
    if (chev) chev.style.transform = open ? 'rotate(180deg)' : '';
    setTimeout(() => window._updateScrollHint?.(), 200);
  }

  /* ─────────────────────────────────────────────
     MODULE ENABLE / DISABLE
     Works for any valid module index (0-11).
  ───────────────────────────────────────────── */
  window.execTogMod = function execTogMod(idx) {
    const cbId = MOD_CB[idx];
    if (!cbId) return; /* index 9 or unknown — ignore */
    const cb = $(cbId);
    window.modEnabled[idx] = cb?.checked ?? false;
    const tglId = MOD_TGL[idx];
    if (tglId) $(tglId)?.classList.toggle('on', window.modEnabled[idx]);
    syncModCount();
    syncRunQueue();
  };

  /* ─────────────────────────────────────────────
     FOOTER COUNT SYNC
  ───────────────────────────────────────────── */
  function syncModCount() {
    const grp = window.grpEnabled;
    const mod = window.modEnabled;

    /* Group 0 — Q Audit: indices 0-5 */
    const qa = grp[0] ? [0, 1, 2, 3, 4, 5].filter(i => mod[i]).length : 0;

    /* Group 1 — Audit Plan: indices 6-12 */
    const ap = grp[1] ? [6, 7, 8, 9, 10, 11, 12].filter(i => mod[i]).length : 0;

    /* Group 2 — Inventory: indices 13-15 */
    const inv = grp[2] ? [13, 14, 15].filter(i => mod[i]).length : 0;

    const tot = qa + ap + inv;

    const mc = $('exec-mod-count'); if (mc) mc.textContent = tot + ' / ' + TOTAL_SUBS;
    const ff = $('exec-foot-fill'); if (ff) ff.style.width = (tot / TOTAL_SUBS * 100) + '%';
  }
  window.syncModCount = syncModCount;

  /* ─────────────────────────────────────────────
     RUN QUEUE  (overridden by queue.js after load)
  ───────────────────────────────────────────── */
  window.syncRunQueue = window.syncRunQueue || function syncRunQueue() {
    /* Minimal fallback — queue.js will replace this */
    const grp = window.grpEnabled;
    const mod = window.modEnabled;
    let anyVisible = false;

    /* Group 0: Q Audit (0-5) */
    for (let i = 0; i <= 5; i++) {
      const on = grp[0] && mod[i];
      const w = $('rqwrap-' + i); if (w) w.style.display = on ? '' : 'none';
      if (on) anyVisible = true;
    }
    /* Group 1: Audit Plan (6-12) */
    for (let i = 6; i <= 12; i++) {
      const on = grp[1] && mod[i];
      const w = $('rqwrap-' + i); if (w) w.style.display = on ? '' : 'none';
      if (on) anyVisible = true;
    }
    /* Group 2: Inventory (13-15) */
    for (let i = 13; i <= 15; i++) {
      const on = grp[2] && mod[i];
      const w = $('rqwrap-' + i); if (w) w.style.display = on ? '' : 'none';
      if (on) anyVisible = true;
    }

    const ee = $('rqempty-all'); if (ee) ee.style.display = anyVisible ? 'none' : '';
  };

  /* ─────────────────────────────────────────────
     AUDIT TYPE SELECTOR
  ───────────────────────────────────────────── */
  window.selectAType = function selectAType(type) {
    const inp = $('A_Type'); if (inp) inp.value = type;
    ['Audit_plan', 'Ad_hoc'].forEach(t => {
      $('atype_' + t)?.classList.toggle('selected', t === type);
    });
    $('audit-plan-sections').style.display = type === 'Audit_plan' ? '' : 'none';
    $('adhoc-sections').style.display = type === 'Ad_hoc' ? '' : 'none';
    const sub = $('audit-tgl-sub');
    if (sub) sub.textContent = type === 'Ad_hoc'
      ? 'Ad-hoc — on-demand, unscheduled audit'
      : 'Audit Plan — schedule & configure';
    syncModCount();
    syncRunQueue();
  };

  /* ─────────────────────────────────────────────
     FREQUENCY CONDITIONAL FIELDS
  ───────────────────────────────────────────── */
  window.onFrequencyChange = function onFrequencyChange() {
    const val = $('ap-frequency')?.value || 'one-time';
    const isM = val === 'Manual';
    const isW = val === 'Weekly';
    const isWM = val === 'Weekly' || val === 'Monthly';
    $('fc-days')?.classList.toggle('hidden', isM);
    $('fc-target-day')?.classList.toggle('hidden', !isW);
    $('fc-target-date')?.classList.toggle('hidden', !isWM);
  };

  /* ─────────────────────────────────────────────
     MAPPING MODE SELECTORS
  ───────────────────────────────────────────── */
  window.selectAuditMappingMode = function selectAuditMappingMode(mode) {
    const inp = $('AUDIT_MAPPING_TYPE'); if (inp) inp.value = mode;
    ['Random', 'By_Category', 'By_Storage'].forEach(m => {
      $('ap_mcard_' + m)?.classList.toggle('selected', m === mode.replace(/ /g, '_'));
    });
  };

  window.selectAMMode = function selectAMMode(mode) {
    const inp = $('AUDITOR_MAPPING_TYPE'); if (inp) inp.value = mode;
    ['Random', 'By_Category', 'By_Storage'].forEach(m => {
      $('mcard_' + m)?.classList.toggle('selected', m === mode.replace(/ /g, '_'));
    });
    ['cg_random', 'cg_category', 'cg_storage'].forEach(id => {
      const el = $(id); if (el) el.style.display = 'none';
    });
    const map = { Random: 'cg_random', 'By Category': 'cg_category', 'By Storage': 'cg_storage' };
    const el = $(map[mode]); if (el) el.style.display = '';
  };

  /* ─────────────────────────────────────────────
     INVENTORY TYPE CARDS
  ───────────────────────────────────────────── */
  window.selectInvType = function selectInvType(type) {
    document.querySelectorAll('.inv-type-card').forEach(c => c.classList.remove('selected'));
    $('invcard_' + type)?.classList.add('selected');
    const idsCard = $('inv-ids-card');
    if (idsCard) idsCard.style.display = type === 'Serialized' ? '' : 'none';
  };

  /* ─────────────────────────────────────────────
     INNER RUN TABS (Logs | Browser)
  ───────────────────────────────────────────── */
  window.switchRunTab = function switchRunTab(tab) {
    document.querySelectorAll('.run-tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.run-tab-pane').forEach(p => p.classList.remove('active'));
    $('rtab-' + tab)?.classList.add('active');
    $('rpane-' + tab)?.classList.add('active');
    if (tab === 'browser') setTimeout(() => window.fitBrowserFrame?.(), 30);
  };

  /* ─────────────────────────────────────────────
     LOGOUT
  ───────────────────────────────────────────── */
  window.doLogout = async function doLogout() {
    try { await fetch('/auth/logout', { method: 'POST' }); } catch (_) { }
    window.location.href = '/login';
  };

  /* ─────────────────────────────────────────────
     ONGOING AUDIT — JSON MAPPING VALIDATOR (v11)
     Validates the oa-mapping textarea in ep10.
     Shows inline error for invalid JSON.
  ───────────────────────────────────────────── */
  window.validateOAMapping = function validateOAMapping(ta) {
    const err = $('oa-mapping-error');
    const hint = $('oa-mapping-hint');
    if (!err || !hint) return;
    try {
      JSON.parse(ta.value);
      err.style.display = 'none';
      hint.style.display = '';
      ta.style.borderColor = '';
      ta.style.outlineColor = '';
    } catch (_) {
      err.style.display = '';
      hint.style.display = 'none';
      ta.style.borderColor = 'var(--rose, #f43f5e)';
      ta.style.outlineColor = 'var(--rose, #f43f5e)';
    }
  };

  /* ─────────────────────────────────────────────
     INIT
  ───────────────────────────────────────────── */
  (function init() {
    for (let i = 0; i < 3; i++) {
      $('sgbody-' + i)?.classList.remove('open');
      $('sbh-' + i)?.classList.remove('open');
      const chev = $('sgchev-' + i); if (chev) chev.style.transform = '';
    }

    window.selectInvType('Serialized');

    syncModCount();
    syncRunQueue();
    window.switchTab('setup');

    document.addEventListener('DOMContentLoaded', () => {
      /* Audit plan sub-toggles affect the mod count / queue */
      ['cb-tz', 'cb-ca'].forEach(id => {
        $(id)?.addEventListener('change', () => {
          syncModCount();
          syncRunQueue();
        });
      });
    });

    console.info('[QA] app.js v11 loaded ✓');
  })();

} // end guard

//final