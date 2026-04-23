/* ═══════════════════════════════════════════════════════════════
   Q-ARunner — utils.js
   Shared utilities used by app.js, run.js, terminal.js, auth.js.
   Load FIRST before any other QA script:
     <script src="/static/js/utils.js"></script>
   ═══════════════════════════════════════════════════════════════ */

/* ── Guard against double-load ── */
if (window.__QA_UTILS_LOADED__) {
  console.warn('[QA] utils.js already loaded — skipping.');
} else {
  window.__QA_UTILS_LOADED__ = true;

  /* ─────────────────────────────────────────────
     STRING HELPERS
  ───────────────────────────────────────────── */

  /**
   * Escape HTML special characters.
   * Single canonical implementation — previously duplicated in
   * app.js, run.js, and terminal.js.
   * @param {*} s
   * @returns {string}
   */
  window.escHtml = function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  };

  /* ─────────────────────────────────────────────
     ANSI ESCAPE HANDLING
     Backend Python scripts emit \x1b[NNm color codes.
     SSE transport sometimes delivers the ESC byte
     intact and sometimes as the literal two chars
     "\x1b" or as the replacement char \u0018 / \u001b.
     Match any of these forms followed by [..m.
  ───────────────────────────────────────────── */
  const ANSI_RE = /(?:\x1b|\u0018|\u009b)\[([\d;]*)m/g;

  const ANSI_FG = {
    30: '#3b4252', 31: '#ef4444', 32: '#22c55e', 33: '#eab308',
    34: '#3b82f6', 35: '#a855f7', 36: '#06b6d4', 37: '#e5e7eb',
    90: '#6b7280', 91: '#f87171', 92: '#4ade80', 93: '#fde047',
    94: '#60a5fa', 95: '#c084fc', 96: '#22d3ee', 97: '#f9fafb',
  };

  /** Strip ANSI escape sequences, returning plain text. */
  window.stripAnsi = function stripAnsi(s) {
    return String(s).replace(ANSI_RE, '');
  };

  /**
   * Convert ANSI-colored text into HTML with <span style="color:..">
   * wrappers. Input is HTML-escaped first; unknown codes close the span.
   */
  window.ansiToHtml = function ansiToHtml(s) {
    const str = String(s);
    let out = '';
    let open = false;
    let last = 0;
    let m;
    ANSI_RE.lastIndex = 0;
    while ((m = ANSI_RE.exec(str)) !== null) {
      out += window.escHtml(str.slice(last, m.index));
      const codes = m[1].split(';').filter(Boolean).map(Number);
      if (!codes.length || codes.includes(0)) {
        if (open) { out += '</span>'; open = false; }
      } else {
        const color = codes.map(c => ANSI_FG[c]).find(Boolean);
        if (color) {
          if (open) out += '</span>';
          out += '<span style="color:' + color + '">';
          open = true;
        }
      }
      last = ANSI_RE.lastIndex;
    }
    out += window.escHtml(str.slice(last));
    if (open) out += '</span>';
    return out;
  };

  /**
   * Current time as HH:MM:SS (24-hour).
   * @returns {string}
   */
  window.tsNow = function tsNow() {
    return new Date().toLocaleTimeString('en-US', {
      hour12: false,
      hour:   '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  /**
   * Format elapsed seconds as HH:MM:SS.
   * @param {number} sec
   * @returns {string}
   */
  window.formatElapsed = function formatElapsed(sec) {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return [h, m, s].map(x => String(x).padStart(2, '0')).join(':');
  };

  /* ─────────────────────────────────────────────
     LOG LINE CLASSIFIER
     Maps a raw log string → CSS class name.
     Used by run.js AND terminal.js.
  ───────────────────────────────────────────── */
  window.logClass = function logClass(raw) {
    const lo = raw.toLowerCase();
    if (
      raw.includes('✅') ||
      lo.includes('[ok]') ||
      lo.includes('[success]') ||
      lo.includes('success')
    ) return 'l-ok';

    if (
      raw.includes('❌') ||
      lo.includes('[error]') ||
      lo.includes('failed')
    ) return 'l-err';

    if (
      raw.includes('⚠') ||
      lo.includes('[warn]') ||
      lo.includes('warning')
    ) return 'l-warn';

    if (lo.includes('skipped') || lo.includes('skip')) return 'l-skip';

    if (
      raw.startsWith('[') ||
      lo.includes('[info]') ||
      raw.includes('→')
    ) return 'l-info';

    if (raw.startsWith('─') || raw.startsWith('—') || raw.startsWith('-'.repeat(4)))
      return 'l-sep';

    return 'l-plain';
  };

  /* ─────────────────────────────────────────────
     THEME
  ───────────────────────────────────────────── */

  /**
   * Apply and persist a theme.
   * Handles both the v8 two-button toggle and the v9 single-icon button.
   * @param {'light'|'dark'} t
   */
  window.setTheme = function setTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem('qa-theme', t);

    // v9 segmented toggle
    const ttLight = document.getElementById('tt-light');
    const ttDark  = document.getElementById('tt-dark');
    if (ttLight) ttLight.classList.toggle('active', t === 'light');
    if (ttDark)  ttDark.classList.toggle('active',  t === 'dark');

    // v8 single icon button
    const iconBtn = document.getElementById('theme-toggle');
    if (iconBtn) iconBtn.textContent = t === 'dark' ? '☀️' : '🌙';
  };

  /** Toggle between light and dark. */
  window.toggleTheme = function toggleTheme() {
    const cur = document.documentElement.getAttribute('data-theme') || 'light';
    window.setTheme(cur === 'dark' ? 'light' : 'dark');
  };

  /** Apply stored theme immediately (call at top of <body>). */
  (function applyStoredTheme() {
    const stored = localStorage.getItem('qa-theme') || 'light';
    window.setTheme(stored);
  })();

  /* ─────────────────────────────────────────────
     ENVIRONMENT SELECTOR
  ───────────────────────────────────────────── */

  /**
   * Activate an env button and sync all env-dependent UI elements.
   * @param {HTMLElement} btn   The clicked .env-btn element
   * @param {string}      env   e.g. 'QA', 'STAGING', 'PROD'
   */
  /**
   * Map nav-button labels to their matching <select> option values.
   * The PROD button is labelled "PROD" but the option value is "PRODUCTION".
   */
  const ENV_LABEL_TO_VALUE = { PROD: 'PRODUCTION', STG: 'STAGING', QA: 'QA', DEV: 'DEV' };
  const ENV_VALUE_TO_LABEL = { PRODUCTION: 'PROD', STAGING: 'STG', QA: 'QA', DEV: 'DEV' };

  window.setEnv = function setEnv(btn, env) {
    // Resolve the canonical select-value from either a label ('PROD') or a full value ('PRODUCTION')
    const selectValue = ENV_LABEL_TO_VALUE[env] || env;
    // Resolve the short display label from either form
    const displayLabel = ENV_VALUE_TO_LABEL[selectValue] || selectValue;

    document.querySelectorAll('.env-btn, .env-tab').forEach(b => {
      b.classList.remove('active', 'dev', 'qa', 'stg', 'prod', 'staging', 'production');
    });
    if (btn) {
      btn.classList.add('active', displayLabel.toLowerCase());
    } else {
      // Called from the <select> onchange — highlight the matching nav button by label text
      document.querySelectorAll('.env-btn, .env-tab').forEach(b => {
        if (b.textContent.trim() === displayLabel) b.classList.add('active', displayLabel.toLowerCase());
      });
    }

    const sel = document.getElementById('environments');
    if (sel && sel.value !== selectValue) sel.value = selectValue;

    ['run-env-disp', 'nav-env-disp'].forEach(id => {
      const el = document.getElementById(id); if (el) el.textContent = displayLabel;
    });
  };

  /* ─────────────────────────────────────────────
     FORM HELPERS
  ───────────────────────────────────────────── */

  /** Safe getElementById value getter. */
  window.fv = function fv(id) {
    return document.getElementById(id)?.value ?? '';
  };

  /** Safe getElementById checked getter. */
  window.fb = function fb(id) {
    return document.getElementById(id)?.checked ?? false;
  };

  /** Get textarea lines as trimmed, non-empty array. */
  window.ftaLines = function ftaLines(id) {
    return window.fv(id).split('\n').map(x => x.trim()).filter(Boolean);
  };

  /* ─────────────────────────────────────────────
     TOGGLE / CHECKBOX HELPERS
     (shared between app.js and inline HTML onclick)
  ───────────────────────────────────────────── */

  /**
   * Sync a row's .on class to a checkbox state.
   * @param {string} cbId   checkbox id
   * @param {string} rowId  container row id (optional)
   */
  window.togField = function togField(cbId, rowId) {
    const cb = document.getElementById(cbId);
    if (!cb) return;
    if (rowId) document.getElementById(rowId)?.classList.toggle('on', cb.checked);
  };

  /**
   * Toggle a styled checkbox card.
   * @param {HTMLElement} el   The .chk-card element
   * @param {string}      id   The hidden <input> id
   */
  window.togChk = function togChk(el, id) {
    const cb = document.getElementById(id);
    if (!cb) return;
    cb.checked = !cb.checked;
    el.classList.toggle('on', cb.checked);
    const box = el.querySelector('.chk-box');
    if (box) box.textContent = cb.checked ? '✓' : '';
  };

  /* ─────────────────────────────────────────────
     FILE UPLOAD DISPLAY
  ───────────────────────────────────────────── */

  /**
   * Update the upload zone UI after a file is picked.
   * If sheetDropdownIds is provided, triggers backend inspection for Excel files.
   * @param {HTMLInputElement} input
   * @param {string} zoneId
   * @param {string} nameId    element that shows filename in zone
   * @param {string} metaId    file-meta bar element
   * @param {string} sizeId    file size display
   * @param {string} fnId      filename display in meta bar
   * @param {string[]} [sheetDropdownIds] IDs of <select> to populate with sheet names
   * @param {string} [statusId] ID of element to show loading/error status
   */
  window.onFilePick = function onFilePick(input, zoneId, nameId, metaId, sizeId, fnId, sheetDropdownIds, statusId) {
    if (!input.files.length) return;
    const f = input.files[0];
    document.getElementById(zoneId)?.classList.add('has-file');
    const nEl = document.getElementById(nameId);
    if (nEl) { nEl.textContent = f.name; nEl.classList.add('chosen'); }
    document.getElementById(metaId)?.classList.add('show');
    const fnEl = document.getElementById(fnId);
    if (fnEl) fnEl.textContent = f.name;
    const szEl = document.getElementById(sizeId);
    if (szEl) szEl.textContent = (f.size / 1_048_576).toFixed(1) + ' MB';

    // If it's an Excel file and we have dropdowns to fill, inspect it.
    const ext = f.name.split('.').pop().toLowerCase();
    if ((ext === 'xlsx' || ext === 'xls') && sheetDropdownIds) {
      window.inspectExcel(input, sheetDropdownIds, statusId);
    }
  };

  /**
   * Post file to /inspect_audit_excel and populate sheet dropdowns.
   * @param {HTMLInputElement} input
   * @param {string[]} dropdownIds
   * @param {string} statusId
   */
  window.inspectExcel = async function inspectExcel(input, dropdownIds, statusId) {
    const f = input.files[0];
    if (!f) return;

    const sEl = document.getElementById(statusId);
    const selects = dropdownIds.map(id => document.getElementById(id)).filter(Boolean);

    try {
      if (sEl) {
        sEl.textContent = '⌛ Inspecting sheets...';
        sEl.style.color = 'var(--accent)';
      }
      selects.forEach(sel => {
        sel.disabled = true;
        sel.innerHTML = '<option>Loading sheets...</option>';
      });

      const fd = new FormData();
      fd.append('file', f);

      const res = await fetch('/inspect_audit_excel', { method: 'POST', body: fd });
      const data = await res.json();

      if (!data.ok) throw new Error(data.errors?.[0] || 'Inspection failed');

      selects.forEach(sel => {
        sel.disabled = false;
        sel.innerHTML = '';
        data.sheet_names.forEach(name => {
          const opt = document.createElement('option');
          opt.value = name;
          opt.textContent = name;
          sel.appendChild(opt);
        });

        // Auto-select default or first
        if (data.default_sheet && data.sheet_names.includes(data.default_sheet)) {
          sel.value = data.default_sheet;
        } else if (data.sheet_names.length) {
          sel.value = data.sheet_names[0];
        }
      });

      if (sEl) {
        sEl.textContent = `✓ Found ${data.sheet_names.length} sheets`;
        sEl.style.color = 'var(--emerald)';
      }

    } catch (err) {
      console.error('[QA] Excel Inspection Error:', err);
      if (sEl) {
        sEl.textContent = '❌ ' + err.message;
        sEl.style.color = 'var(--rose)';
      }
      selects.forEach(sel => {
        sel.innerHTML = `<option value="">Error: ${err.message}</option>`;
      });
    }
  };

  /* ─────────────────────────────────────────────
     PASSWORD VISIBILITY TOGGLE
  ───────────────────────────────────────────── */

  /**
   * Toggle password field visibility.
   * @param {string}      inputId
   * @param {HTMLElement} btn
   */
  window.togglePw = function togglePw(inputId, btn) {
    const inp = document.getElementById(inputId);
    if (!inp) return;
    const shown = inp.type === 'text';
    inp.type = shown ? 'password' : 'text';
    btn.textContent = shown ? 'Show' : 'Hide';
  };

  /* ─────────────────────────────────────────────
     CLIPBOARD / FILE SAVE
  ───────────────────────────────────────────── */

  /**
   * Copy element inner text to clipboard.
   * @param {string} id
   */
  window.copyElText = function copyElText(id) {
    navigator.clipboard.writeText(
      document.getElementById(id)?.innerText || ''
    ).catch(() => {});
  };

  /**
   * Trigger a download of text content as a .log file.
   * @param {string[]} lines
   * @param {string}   [prefix='qaudit']
   */
  window.saveTextLog = function saveTextLog(lines, prefix) {
    const a = document.createElement('a');
    const ts = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    a.href = URL.createObjectURL(
      new Blob([lines.join('\n')], { type: 'text/plain' })
    );
    a.download = (prefix || 'qaudit') + '_' + ts + '.log';
    a.click();
  };

  /* ─────────────────────────────────────────────
     RESIZE OBSERVER FACTORY
     Returns an observer AND a cleanup function so
     callers can always disconnect when done.
  ───────────────────────────────────────────── */

  /**
   * Create a ResizeObserver that automatically tracks its targets
   * so it can be fully disconnected via the returned cleanup fn.
   * @param {Function} cb   ResizeObserver callback
   * @returns {{ observe: Function, disconnect: Function }}
   */
  window.makeSafeObserver = function makeSafeObserver(cb) {
    const ro = new ResizeObserver(cb);
    const targets = new Set();
    return {
      observe(el) {
        if (!el) return;
        targets.add(el);
        ro.observe(el);
      },
      disconnect() {
        ro.disconnect();
        targets.clear();
      },
    };
  };

  console.info('[QA] utils.js loaded ✓');
}