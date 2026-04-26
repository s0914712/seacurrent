/* SeaCurrent — theme toggle.
 * Reads localStorage('sc:theme') ∈ {'dark','light'} or falls back to prefers-color-scheme.
 * Sets <html data-theme="..."> so tokens.css overrides apply.
 * Exposes window.SeaTheme.{get,set,toggle} for the sea-header button.
 */
(function () {
  var KEY = 'sc:theme';
  var root = document.documentElement;

  function preferred() {
    try {
      return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    } catch (e) { return 'dark'; }
  }

  function read() {
    try { return localStorage.getItem(KEY) || preferred(); }
    catch (e) { return preferred(); }
  }

  function apply(t) {
    root.setAttribute('data-theme', t);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', t === 'light' ? '#f5f7fb' : '#0a1628');
  }

  function set(t) {
    if (t !== 'light' && t !== 'dark') return;
    try { localStorage.setItem(KEY, t); } catch (e) {}
    apply(t);
    window.dispatchEvent(new CustomEvent('sc:theme-change', { detail: { theme: t } }));
  }

  apply(read());

  window.SeaTheme = {
    get: read,
    set: set,
    toggle: function () { set(read() === 'light' ? 'dark' : 'light'); },
  };
})();
