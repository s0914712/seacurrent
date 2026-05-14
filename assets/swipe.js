/* SeaCurrent — swipe gesture helper for collapsible side panels.
 *
 * Looks for elements with [data-swipe-panel] and a sibling/descendant toggle
 * identified by [data-swipe-toggle="<id>"] (defaults to data-swipe-panel
 * attribute value), then dispatches a synthetic click on the toggle when the
 * user drags far enough in the configured direction.
 *
 * Markup contract (added unobtrusively to existing buttons, no JS rewrite):
 *   <div id="sidebar" data-swipe-panel="vertical" data-swipe-target="sidebarToggle">
 *     ... existing markup ...
 *     <button id="sidebarToggle">▲</button>   <!-- existing toggle -->
 *   </div>
 *
 * Guards:
 *   - skipped when prefers-reduced-motion: reduce
 *   - skipped when pointerType === 'mouse' (mouse uses the button as before)
 *   - skipped when viewport is wider than 767.98px
 *   - listens on the panel itself but ignores events that originated from
 *     interactive descendants (form fields, the toggle button, Leaflet panes)
 */
(function () {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const THRESHOLD = 40;           // pixels
  const MAX_DURATION = 500;       // ms; longer drags treated as scroll, not swipe
  const INTERACTIVE = 'input, select, textarea, button, a, [contenteditable], .leaflet-container, .leaflet-control, .tl-range, sea-next-step';

  function isPhone() {
    return window.matchMedia('(max-width: 767.98px)').matches;
  }

  function attach(panel) {
    let startX = 0, startY = 0, startT = 0, active = false;
    const dir = panel.dataset.swipePanel || 'vertical';
    const toggleId = panel.dataset.swipeTarget;
    const handleSel = panel.dataset.swipeHandle;

    function getToggle() {
      return toggleId ? document.getElementById(toggleId) : null;
    }
    function fire() {
      const t = getToggle();
      if (t) t.click();
    }

    panel.addEventListener('pointerdown', e => {
      if (!isPhone()) return;
      if (e.pointerType === 'mouse') return;
      if (e.target.closest(INTERACTIVE)) return;
      if (handleSel && !e.target.closest(handleSel)) return;
      startX = e.clientX;
      startY = e.clientY;
      startT = e.timeStamp;
      active = true;
    }, { passive: true });

    panel.addEventListener('pointerup', e => {
      if (!active) return;
      active = false;
      const dt = e.timeStamp - startT;
      if (dt > MAX_DURATION) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      if (dir === 'vertical') {
        if (Math.abs(dy) < THRESHOLD) return;
        if (Math.abs(dy) <= Math.abs(dx)) return;
        fire();
      } else {
        if (Math.abs(dx) < THRESHOLD) return;
        if (Math.abs(dx) <= Math.abs(dy)) return;
        fire();
      }
    }, { passive: true });

    panel.addEventListener('pointercancel', () => { active = false; }, { passive: true });
  }

  function init() {
    document.querySelectorAll('[data-swipe-panel]').forEach(attach);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
