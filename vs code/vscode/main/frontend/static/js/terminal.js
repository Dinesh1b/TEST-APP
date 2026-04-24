/* ═══════════════════════════════════════════════════════════════
   Q-ARunner — terminal.js  (v9 clean)
   Used by: terminal.html (standalone full-page terminal)

   KEY CHANGE from old version:
     ✗ Old: auto-started SSE in an IIFE on page load — meant every
            time the iframe loaded, it opened a new /stream connection
            even if no run was active, competing with run.js.
     ✓ New: waits for either:
            (a) a postMessage from the parent window: { type:'qa-start-stream' }
            (b) the ?autostart=1 query param  (for direct-page use only)
            This way, only ONE consumer ever connects to /stream.

   Depends on: utils.js (escHtml, tsNow, formatElapsed, logClass)
   ═══════════════════════════════════════════════════════════════ */
'use strict';

/* ── Apply stored theme immediately ── */
(function () {
  const t = localStorage.getItem('qa-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', t);
})();

/* ─────────────────────────────────────────────
   STATE
───────────────────────────────────────────── */
let _evtSrc    = null;
let _t0        = Date.now();
let _tickTimer = null;
let _lines     = [];
let _cOk = 0, _cErr = 0;
let _streamStarted = false;
// Prevent polling loop from overlapping itself
let _pollBusy  = false;

/* ─────────────────────────────────────────────
   HELPERS (local fallbacks if utils.js absent)
───────────────────────────────────────────── */
const escHtml = window.escHtml || (s =>
  String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
);
const tsNow = window.tsNow || (() =>
  new Date().toLocaleTimeString('en-US',{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'})
);
const logCls = window.logClass || (raw => {
  const lo = raw.toLowerCase();
  if (raw.includes('✅') || lo.includes('[ok]') || lo.includes('success')) return 'ok';
  if (raw.includes('❌') || lo.includes('[error]') || lo.includes('failed')) return 'err';
  if (raw.includes('⚠')  || lo.includes('[warn]'))  return 'warn';
  if (lo.includes('skipped')) return 'skip';
  if (raw.startsWith('[') || raw.includes('→')) return 'info';
  return 'plain';
});

/* ─────────────────────────────────────────────
   UI HELPERS
───────────────────────────────────────────── */
function setChip(state, txt) {
  const c = document.getElementById('chip');
  if (c) c.className = 'chip ' + state;
  const ct = document.getElementById('chipTxt');
  if (ct) ct.textContent = txt;
  const ft = document.getElementById('footTxt');
  if (ft) ft.textContent = txt;
}

function updateFooter() {
  const elapsed = Math.floor((Date.now() - _t0) / 1000);
  const m = Math.floor(elapsed / 60);
  const s = elapsed % 60;
  const r = document.getElementById('footR');
  if (r) r.textContent = _lines.length + ' lines · ' + (m > 0 ? m + 'm ' + s + 's' : elapsed + 's');
}

function addLine(raw) {
  const t = document.getElementById('term');
  if (!t) return;

  // Remove placeholder on first real line
  const ph = t.querySelector('.skip');
  if (ph && /waiting/i.test(ph.textContent)) ph.remove();

  const plain = window.stripAnsi ? window.stripAnsi(raw) : raw;
  const c = logCls(plain);
  if (c === 'ok')  _cOk++;
  if (c === 'err') _cErr++;
  _lines.push(plain);

  const ok = document.getElementById('sOk');   if (ok)  ok.textContent  = _cOk;
  const er = document.getElementById('sErr');  if (er)  er.textContent  = _cErr;
  const sl = document.getElementById('sLines');if (sl)  sl.textContent  = _lines.length;

  const span = document.createElement('span');
  span.className = 'line ' + c;
  span.innerHTML = (window.ansiToHtml ? window.ansiToHtml(raw) : escHtml(plain)) + '\n';
  t.appendChild(span);
  t.scrollTop = t.scrollHeight;
  updateFooter();
}

/* ─────────────────────────────────────────────
   PROGRESS BAR
───────────────────────────────────────────── */
function setProgress(pct, label) {
  const f = document.getElementById('pFill');
  if (f) {
    f.classList.remove('ind');
    f.style.width = pct + '%';
  }
  const p = document.getElementById('pPct');
  if (p) p.textContent = pct + '%';
  if (label) {
    const l = document.getElementById('pLabel');
    if (l) l.textContent = label;
  }
}

/* ─────────────────────────────────────────────
   FINISH
───────────────────────────────────────────── */
function finishRun(state) {
  clearInterval(_tickTimer);
  _streamStarted = false;

  const f = document.getElementById('pFill');
  if (f) f.classList.remove('ind');

  if (state === 'done') {
    if (f) { f.style.width = '100%'; f.classList.add('done'); }
    const p = document.getElementById('pPct');    if (p) p.textContent = '100%';
    const l = document.getElementById('pLabel');  if (l) l.textContent = 'All modules completed ✓';
    setChip('done', 'DONE');
  } else {
    if (f) f.classList.add('err');
    const l = document.getElementById('pLabel');  if (l) l.textContent = 'Run ended with errors';
    setChip('error', 'ERROR');
  }
}

/* ─────────────────────────────────────────────
   STREAM  — called only once per run
───────────────────────────────────────────── */
function startStream() {
  if (_streamStarted) {
    console.warn('[terminal] startStream() called again — ignored.');
    return;
  }
  _streamStarted = true;
  _t0 = Date.now();

  setChip('running', 'RUNNING');

  clearInterval(_tickTimer);
  _tickTimer = setInterval(updateFooter, 1000);

  if (_evtSrc) { _evtSrc.close(); _evtSrc = null; }
  _evtSrc = new EventSource('/stream');

  _evtSrc.onmessage = e => {
    const raw = e.data;
    if (raw === '__DONE__')  { _evtSrc.close(); _evtSrc = null; clearInterval(_tickTimer); finishRun('done');  return; }
    if (raw === '__ERROR__') { _evtSrc.close(); _evtSrc = null; clearInterval(_tickTimer); finishRun('error'); return; }
    try {
      const obj = JSON.parse(raw);
      if (obj.type === 'progress') {
        setProgress(obj.progress || 0, obj.step ? 'Running: ' + obj.step : null);
        return;
      }
    } catch (_) {}
    addLine(raw);
  };

  _evtSrc.onerror = () => {
    clearInterval(_tickTimer);
    finishRun('error');
  };
}

/* ─────────────────────────────────────────────
   TOOLBAR ACTIONS (called from HTML onclick)
───────────────────────────────────────────── */
window.clearT = function () {
  const t = document.getElementById('term');
  if (t) t.innerHTML = '<span class="line skip">// Log cleared.</span>';
  _lines = []; _cOk = 0; _cErr = 0;
  ['sOk','sErr','sLines'].forEach(id => {
    const el = document.getElementById(id); if (el) el.textContent = '0';
  });
};

window.copyAll = function () {
  navigator.clipboard.writeText(_lines.join('\n'));
};

window.saveLog = function () {
  if (window.saveTextLog) {
    window.saveTextLog(_lines, 'qaudit_terminal');
    return;
  }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([_lines.join('\n')], { type: 'text/plain' }));
  a.download = 'qaudit_' + new Date().toISOString().slice(0,19).replace(/:/g,'-') + '.log';
  a.click();
};

window.finishRun = finishRun; // expose for toolbar Stop button

/* ─────────────────────────────────────────────
   TRIGGER: postMessage from parent  OR  ?autostart
   ─────────────────────────────────────────────
   Parent (index.html / run.js) sends:
     iframeEl.contentWindow.postMessage({ type: 'qa-start-stream' }, '*');
   Or for standalone use, open as:
     /terminal?autostart=1
───────────────────────────────────────────── */
window.addEventListener('message', e => {
  if (e.data && e.data.type === 'qa-start-stream') {
    startStream();
  }
  if (e.data && e.data.type === 'qa-stop-stream') {
    if (_evtSrc) { _evtSrc.close(); _evtSrc = null; }
    clearInterval(_tickTimer);
    finishRun('error');
  }
});

/* Auto-start only when explicitly requested via URL param */
(function checkAutostart() {
  const params = new URLSearchParams(window.location.search);
  if (params.get('autostart') === '1') {
    startStream();
  }
  // Otherwise stay idle — do NOT open /stream automatically
})();

/* ─────────────────────────────────────────────
   POLL /browser_status (for HUD) with overlap guard
───────────────────────────────────────────── */
async function pollStatus() {
  if (_pollBusy) return;
  _pollBusy = true;
  try {
    const r = await fetch('/browser_status?_=' + Date.now());
    const d = await r.json();
    const hud    = document.getElementById('hud');
    const hudTxt = document.getElementById('hud-txt');
    if (d.running || d.has_screenshot) {
      if (hud)    hud.classList.add('visible');
      if (hudTxt) hudTxt.textContent = d.running
        ? 'LIVE — RUN #' + (d.run_id || '—')
        : 'LAST RUN — '  + (d.run_id || '—');
    }
  } catch (_) {
    // silently ignore — server may not have this endpoint
  } finally {
    _pollBusy = false;
  }
}

setInterval(pollStatus, 3000); // reduced from 2 s to ease server load