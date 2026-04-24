/* ═══════════════════════════════════════════════════════════════
   Q-ARunner — run.js  (v12)
   Handles: SSE stream, /run POST, /stop, timer, progress,
            log terminal.

   FIX v12: removed _stopLive() call in _finishRun — that
            function was never defined, causing a ReferenceError
            that silently killed the entire module.
═══════════════════════════════════════════════════════════════ */
'use strict';

if (window.__QA_RUN_LOADED__) {
  console.warn('[QA] run.js already loaded — skipping duplicate.');
} else {
  window.__QA_RUN_LOADED__ = true;

  /* ─────────────────────────────────────────────
     MODULE STATE
  ───────────────────────────────────────────── */
  let _evtSrc       = null;
  let _elapsedTimer = null;
  let _elapsedSec   = 0;
  let _simInt       = null;
  let _sbObserver   = null;
  let _autoScroll   = true;
  let _running      = false;
  let _lastErrLine  = '';
  let _logLines     = [];
  let _logOk = 0, _logErr = 0, _logWarn = 0;

  window._uploadedPaths = window._uploadedPaths || {};
  /* modEnabled is owned by app.js (length 16). Do not re-initialize here —
     a fallback literal would lock a stale length via the `||` short-circuit. */
  window.grpEnabled     = window.grpEnabled     || [false, false, false];


  /* ─────────────────────────────────────────────
     SAFE DOM HELPERS
  ───────────────────────────────────────────── */
  const $   = id  => document.getElementById(id);
  const set = (id, val)  => { const el = $(id); if (el) el.textContent = val; };
  const show = (id, disp) => { const el = $(id); if (el) el.style.display = disp || ''; };
  const hide = id => { const el = $(id); if (el) el.style.display = 'none'; };

  /* ─────────────────────────────────────────────
     TIMER
  ───────────────────────────────────────────── */
  function _startTimer() {
    clearInterval(_elapsedTimer);
    _elapsedSec   = 0;
    _elapsedTimer = setInterval(() => {
      _elapsedSec++;
      const str = window.formatElapsed
        ? window.formatElapsed(_elapsedSec)
        : [Math.floor(_elapsedSec / 3600), Math.floor((_elapsedSec % 3600) / 60), _elapsedSec % 60]
            .map(x => String(x).padStart(2, '0')).join(':');
      ['elapsedBadge', 'run-elapsed-inner'].forEach(id => set(id, str));
      const badge = $('elapsedBadge');
      if (badge) badge.className = 'elapsed-badge running';
    }, 1000);
  }

  function _stopTimer() {
    clearInterval(_elapsedTimer);
    _elapsedTimer = null;
  }

  /* ─────────────────────────────────────────────
     STATUS PILL
  ───────────────────────────────────────────── */
  function _setStatus(cls, txt) {
    const pill = $('statusPill');
    if (pill) pill.className = 'status-pill ' + cls;
    set('statusTxt', txt);
  }

  /* ─────────────────────────────────────────────
     PROGRESS
  ───────────────────────────────────────────── */
  function _setProgress(pct, label) {
    ['run-fill', 'srs-fill', 'run-sb-fill'].forEach(id => {
      const el = $(id); if (el) el.style.width = pct + '%';
    });
    ['run-pct-big', 'srs-pct'].forEach(id => set(id, pct + '%'));
    if (label) {
      ['run-prog-label', 'run-sub-text', 'srs-mod'].forEach(id => set(id, label));
    }
  }

  /* ─────────────────────────────────────────────
     TERMINAL LOG
  ───────────────────────────────────────────── */
  function _updateStats() {
    set('ts-ok-count',  _logOk);
    set('ts-err-count', _logErr);
    set('ts-warn-count',_logWarn);
    set('ts-lines', _logLines.length + ' lines');
  }

  function _appendLog(raw, forceCls) {
    const plain = window.stripAnsi ? window.stripAnsi(raw) : raw;
    _logLines.push(plain);
    const cls = forceCls || (window.logClass ? window.logClass(plain) : _defaultLogClass(plain));
    if (cls === 'l-ok')  _logOk++;
    if (cls === 'l-err') { _logErr++; _lastErrLine = plain; }
    if (cls === 'l-warn') _logWarn++;
    _updateStats();

    const t = $('run-terminal');
    if (!t) return;

    const cur = t.querySelector('.term-cursor');
    if (cur) cur.remove();

    const ts  = window.tsNow
      ? window.tsNow()
      : new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const msgHtml = window.ansiToHtml
      ? window.ansiToHtml(raw)
      : (window.escHtml
          ? window.escHtml(plain)
          : plain.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'));

    const span = document.createElement('span');
    span.className = 'log ' + cls;
    span.innerHTML = `<span class="ts">${ts}</span><span class="msg">${msgHtml}</span>\n`;
    t.appendChild(span);

    const c = document.createElement('span');
    c.className = 'term-cursor';
    t.appendChild(c);

    if (_autoScroll) t.scrollTop = t.scrollHeight;
  }

  function _defaultLogClass(raw) {
    const l = raw.toLowerCase();
    if (l.includes('success') || l.includes('[ok]') || l.includes('✅'))  return 'l-ok';
    if (l.includes('[error]')  || l.includes('failed') || l.includes('❌')) return 'l-err';
    if (l.includes('[warn]')   || l.includes('warning'))                    return 'l-warn';
    if (raw.startsWith('['))    return 'l-info';
    if (raw.startsWith('─') || raw.startsWith('-')) return 'l-sep';
    return 'l-plain';
  }

  /* ─────────────────────────────────────────────
     SSE STREAM
  ───────────────────────────────────────────── */
  function _openStream() {
    if (_evtSrc) { _evtSrc.close(); _evtSrc = null; }

    _evtSrc = new EventSource('/stream');

    _evtSrc.onmessage = e => {
      const raw = e.data;
      if (raw === '__DONE__')  { _evtSrc.close(); _evtSrc = null; _finishRun('done');  return; }
      if (raw === '__ERROR__') { _evtSrc.close(); _evtSrc = null; _finishRun('error'); return; }
      try {
        const obj = JSON.parse(raw);
        if (obj.type === 'progress') { _setProgress(obj.progress || 0, obj.step ? '▶ ' + obj.step : null); return; }
      } catch (_) {}
      _appendLog(raw);
    };

    _evtSrc.onerror = () => {
      if (_evtSrc) { _evtSrc.close(); _evtSrc = null; }
      _finishRun('error');
    };
  }

  /* ─────────────────────────────────────────────
     DEMO SIMULATION
  ───────────────────────────────────────────── */
  function _runSimulate() {
    const active = (window.QA_MODULES || []).filter(m => {
      const ge = window.grpEnabled || [];
      const me = window.modEnabled || [];
      return !!(ge[m.group] && me[m.idx]);
    });
    if (!active.length) {
      _appendLog('[WARN] No modules enabled.', 'l-warn');
      _finishRun('done');
      return;
    }
    let idx = 0, pct = 0;
    clearInterval(_simInt);
    _simInt = setInterval(() => {
      if (idx >= active.length) { clearInterval(_simInt); _finishRun('done'); return; }
      const target = Math.round(((idx + 1) / active.length) * 100);
      pct = Math.min(pct + 3, target);
      _setProgress(pct, 'Running: ' + active[idx].name + ' (' + (idx + 1) + '/' + active.length + ')');
      if (pct >= target) {
        _appendLog('[SUCCESS] ' + active[idx].name + ' completed successfully.', 'l-ok');
        idx++;
      }
    }, 70);
  }

  /* ─────────────────────────────────────────────
     FILE UPLOAD
  ───────────────────────────────────────────── */
  async function _uploadFiles() {
    for (const inp of document.querySelectorAll('input[type=file]')) {
      if (!inp.files.length) continue;
      const fd = new FormData();
      fd.append('file', inp.files[0]);
      try {
        const res  = await fetch('/upload', { method: 'POST', body: fd });
        const data = await res.json();
        if (data.path) {
          const keyMap = { 'file-qs': 'EXCEL_PATH', 'file-ii': 'IMPORT_EXCEL', 'file-oa': 'OA_EXCEL' };
          const key    = keyMap[inp.id] || inp.id || 'EXCEL_PATH';
          window._uploadedPaths[key] = data.path;
        }
      } catch (_) {}
    }
  }

  /* ─────────────────────────────────────────────
     RESET UI
  ───────────────────────────────────────────── */
  function _resetUI(runId) {
    _logLines = []; _logOk = 0; _logErr = 0; _logWarn = 0; _lastErrLine = '';
    _updateStats();

    const t = $('run-terminal');
    if (t) t.innerHTML = '<span class="term-cursor"></span>';

    ['run-fill', 'srs-fill', 'run-sb-fill'].forEach(id => {
      const el = $(id); if (!el) return;
      el.classList.remove('done', 'err');
      el.style.width     = '0%';
      el.style.animation = '';
    });
    _setProgress(0, 'Initializing...');

    set('run-id-disp',       '#' + runId);
    set('run-env-disp',      (window.fv ? window.fv('environments') : null) || 'QA');
    set('run-elapsed-inner', '00:00:00');
    set('elapsedBadge',      '00:00:00');
    set('srs-id',            '#' + runId);
    set('srs-label',         'RUNNING');
    set('srs-mod',           'Initializing...');
    set('srs-pct',           '0%');
    set('run-sb-status',     'RUNNING');

    const eb = $('elapsedBadge');
    if (eb) eb.className = 'elapsed-badge running';

    hide('sb-run-empty');
    show('sb-run-state', 'flex');
    const dot = $('srs-dot');
    if (dot) { dot.style.animation = ''; dot.style.background = 'var(--emerald)'; }

    show('run-strip', 'flex');
    show('run-stop-btn',  'block');
    hide('run-rerun-btn');
    show('run-prog-card');
    $('run-err-surface')?.classList.remove('show');
    $('run-live-dot')?.classList.add('live');
    set('run-term-lbl', 'Live Output');
    const sd = $('run-sub-dot'); if (sd) sd.style.opacity = '1';
  }

  /* ─────────────────────────────────────────────
     FINISH RUN
  ───────────────────────────────────────────── */
  function _finishRun(state) {
    _stopTimer();
    clearInterval(_simInt);
    _running = false;

    // NOTE: _stopLive() intentionally removed — it was never defined
    // and caused a ReferenceError that crashed the module silently.

    hide('run-stop-btn');
    show('run-rerun-btn', 'block');
    $('run-live-dot')?.classList.remove('live');
    set('run-term-lbl', 'Output Log');
    const sd = $('run-sub-dot'); if (sd) sd.style.opacity = '0';
    document.querySelectorAll('.term-cursor').forEach(c => {
      c.style.animationPlayState = 'paused';
    });

    const applyState = cls => {
      ['run-fill', 'srs-fill', 'run-sb-fill'].forEach(id => {
        const el = $(id); if (!el) return;
        el.classList.add(cls);
        el.style.animation = 'none';
      });
    };

    if (state === 'done') {
      applyState('done');
      ['run-fill', 'srs-fill'].forEach(id => {
        const el = $(id); if (el) el.style.width = '100%';
      });
      _setProgress(100, '✓ All modules completed');
      _setStatus('done', 'DONE');
      _appendLog('[SUCCESS] Run completed ✓', 'l-ok');
      const dot = $('srs-dot');
      if (dot) { dot.style.animation = 'none'; dot.style.background = 'var(--sky)'; }
      set('srs-label',    'DONE');
      set('srs-mod',      '✓ Done');
      set('srs-pct',      '100%');
      set('run-sb-status','DONE');
    } else {
      applyState('err');
      _setStatus('error', 'ERROR');
      _appendLog('[ERROR] Run ended with errors.', 'l-err');
      $('run-err-surface')?.classList.add('show');
      set('run-err-msg', _lastErrLine || 'An error occurred. Check the output log above.');
      const dot = $('srs-dot');
      if (dot) { dot.style.animation = 'none'; dot.style.background = 'var(--rose)'; }
      set('srs-label',    'ERROR');
      set('run-sb-status','ERROR');
    }
  }

  /* ─────────────────────────────────────────────
     PUBLIC RUN API
  ───────────────────────────────────────────── */
  window.startRun = async function startRun() {
    if (_running) {
      console.warn('[QA] startRun() called while already running — ignored.');
      return;
    }
    _running = true;

    const runId = Math.random().toString(36).slice(2, 8).toUpperCase();
    _resetUI(runId);
    _setStatus('running', 'RUNNING');

    const btn = $('run-now-btn');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
        'stroke-width="2.5" style="animation:spin .7s linear infinite">' +
        '<path d="M21 12a9 9 0 11-18 0"/></svg> STARTING...';
    }

    _startTimer();

    if (typeof window.ensureImportItemExcelReady === 'function') {
      const ok = await window.ensureImportItemExcelReady();
      if (!ok) { _finishRun('error'); return; }
    }
    if (typeof window.ensureAuditBaseReady === 'function') {
      const ok = await window.ensureAuditBaseReady();
      if (!ok) { _finishRun('error'); return; }
    }

    await _uploadFiles();

    if (typeof window.syncRunQueue === 'function') {
      window.syncRunQueue();
      await new Promise(r => setTimeout(r, 100));
    }

    const cfg = window.buildCfg ? window.buildCfg() : {};
    try {
      const res  = await fetch('/run', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(cfg),
      });
      const data = await res.json();
      _appendLog(
        '[INFO] Run #' + (data.run_id || runId) + ' started — ' + data.total + ' module(s) queued',
        'l-info'
      );
      _openStream();
    } catch (err) {
      _appendLog('[WARN] Server unavailable — demo simulation', 'l-warn');
      _runSimulate();
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML =
          '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">' +
          '<polygon points="5 3 19 12 5 21"/></svg> RUN NOW';
      }
    }
  };

  window.stopRun = function stopRun() {
    fetch('/stop', { method: 'POST' }).catch(() => {});
    if (_evtSrc) { _evtSrc.close(); _evtSrc = null; }
    clearInterval(_simInt);
    _appendLog('[WARN] Run stopped by user.', 'l-warn');
    _finishRun('error');
  };

  window.rerunRun = function rerunRun() {
    ['run-fill', 'srs-fill'].forEach(id => {
      const el = $(id); if (!el) return;
      el.classList.remove('done', 'err');
      el.style.animation = '';
    });
    $('run-err-surface')?.classList.remove('show');
    const eb = $('elapsedBadge');
    if (eb) { eb.textContent = '00:00:00'; eb.className = 'elapsed-badge'; }
    _running = false;
    window.startRun();
  };

  /* ─────────────────────────────────────────────
     TERMINAL CONTROLS
  ───────────────────────────────────────────── */
  window.copyLog = function () {
    navigator.clipboard.writeText(_logLines.join('\n')).catch(() => {});
  };

  window.saveLog = function () {
    const ts  = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const a   = document.createElement('a');
    a.href     = URL.createObjectURL(new Blob([_logLines.join('\n')], { type: 'text/plain' }));
    a.download = 'qaudit_' + ts + '.log';
    a.click();
  };

  window.clearLog = function (id) {
    const el = $(id || 'run-terminal');
    if (el) el.innerHTML =
      '<span class="log l-skip"><span class="msg">// Log cleared.</span></span>' +
      '<span class="term-cursor"></span>';
    _logLines = []; _logOk = 0; _logErr = 0; _logWarn = 0;
    _updateStats();
  };

  window.toggleAutoScroll = function () {
    _autoScroll = !_autoScroll;
    const b = $('run-as-btn');
    if (b) {
      b.textContent = _autoScroll ? '↓ Auto' : '↕ Manual';
      b.classList.toggle('toggled', _autoScroll);
    }
  };

  /* ─────────────────────────────────────────────
     HISTORY
  ───────────────────────────────────────────── */
  async function _loadHistory() {
    try {
      const data = await (await fetch('/history')).json();
      const wrap = $('history-list'); if (!wrap) return;
      if (!data.length) {
        wrap.innerHTML = '<div style="color:var(--t4);font-size:11px;padding:8px 6px;font-style:italic;">No runs yet</div>';
        return;
      }
      const seen = {};
      data.forEach(r => { if (!seen[r.run_id] || r.ended_at) seen[r.run_id] = r; });
      wrap.innerHTML = Object.values(seen).slice(0, 12).map(r => {
        const st = r.ended_at ? r.status : 'run';
        const t  = r.started_at
          ? new Date(r.started_at * 1000).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
          : '—';
        return `<div class="hist-item">
          <span class="hist-id">#${r.run_id || '?'}</span>
          <span class="hist-step">${r.step || '—'}</span>
          <span class="hist-badge ${st}">${st.toUpperCase()}</span>
        </div>`;
      }).join('');
    } catch (_) {}
  }
  window.loadHistory = _loadHistory;

  /* ─────────────────────────────────────────────
     SIDEBAR SCROLL HINT
  ───────────────────────────────────────────── */
  function _initSidebarScrollHint() {
    const sbExec = $('sb-exec-scroll');
    const sbHint = $('sb-scroll-hint');
    if (!sbExec || !sbHint) return;
    const THRESH = 12;
    function update() {
      const ep = $('sb-execution');
      if (!ep || !ep.classList.contains('visible')) { sbHint.classList.remove('visible'); return; }
      const atBottom    = sbExec.scrollHeight - sbExec.scrollTop - sbExec.clientHeight <= THRESH;
      const hasOverflow = sbExec.scrollHeight > sbExec.clientHeight + THRESH;
      sbHint.classList.toggle('visible', hasOverflow && !atBottom);
    }
    sbExec.addEventListener('scroll', update, { passive: true });
    if (window.makeSafeObserver) {
      _sbObserver = window.makeSafeObserver(update);
      _sbObserver.observe(sbExec);
    }
    window._updateScrollHint = update;
  }

  /* ─────────────────────────────────────────────
     INIT
  ───────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', () => {
    const t = $('run-terminal');
    if (t) {
      t.addEventListener('scroll', () => {
        _autoScroll = (t.scrollHeight - t.scrollTop - t.clientHeight) < 40;
      });
    }
    _initSidebarScrollHint();
    _loadHistory();
    setInterval(_loadHistory, 30000);
  });

  console.info('[QA] run.js v12 loaded ✓');

} // end duplicate-load guard