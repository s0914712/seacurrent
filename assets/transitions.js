/* SeaCurrent — cross-page View Transitions wrapper.
 * Intercepts same-origin nav clicks inside shared shell components
 * (sea-header, sea-tabbar, sea-footer, sea-next-step) and runs the
 * navigation inside document.startViewTransition() when supported,
 * giving a soft cross-fade instead of a hard white flash.
 *
 * Falls back to native navigation when:
 *   - View Transitions API is unavailable (Firefox, older Safari)
 *   - prefers-reduced-motion: reduce
 *   - modifier keys held (cmd/ctrl/shift/alt) or middle-click
 *   - target is external, mailto:, tel:, or has download attribute
 */
(function () {
  if (!('startViewTransition' in document)) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const SHELL_TAGS = new Set(['SEA-HEADER', 'SEA-TABBAR', 'SEA-FOOTER', 'SEA-NEXT-STEP']);

  function fromShell(target) {
    let n = target;
    while (n) {
      if (n.nodeType === 1 && SHELL_TAGS.has(n.tagName)) return true;
      n = n.parentNode || (n.host /* shadow root */);
    }
    return false;
  }

  function handle(e) {
    if (e.defaultPrevented) return;
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

    const path = e.composedPath ? e.composedPath() : [];
    const link = path.find(n => n && n.tagName === 'A' && n.href);
    if (!link) return;
    if (!fromShell(link)) return;
    if (link.target && link.target !== '_self') return;
    if (link.hasAttribute('download')) return;

    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin) return;
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return;
    if (url.pathname === location.pathname && url.search === location.search) return;

    e.preventDefault();
    document.startViewTransition(() => {
      location.assign(url.href);
    });
  }

  document.addEventListener('click', handle, true);
})();
