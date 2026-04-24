/* ═══════════════════════════════════════════════════════════════
   Q-ARunner — tabs.js
   Inner run-tab switching (Logs | Browser).
   switchRunTab() is defined in app.js.
   This file wires any .run-tab-btn[data-tab] elements that use
   the class-based pattern instead of inline onclick.
   Safe to include even if no such buttons exist in the HTML.
═══════════════════════════════════════════════════════════════ */
'use strict';

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.run-tab-btn[data-tab]').forEach(btn => {
    if (btn.dataset.tabInit) return;
    btn.dataset.tabInit = '1';
    btn.addEventListener('click', () => {
      if (typeof window.switchRunTab === 'function') {
        window.switchRunTab(btn.dataset.tab);
      }
    });
  });
});