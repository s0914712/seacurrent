/* SeaCurrent — theme-aware CartoDB basemap tile layer.
 *
 * Usage:
 *   var tile = SeaTiles.addTo(map, { attribution: '...' });
 *
 * Returns a Leaflet tileLayer that swaps between dark_all / light_all
 * whenever <html data-theme> flips (via the sc:theme-change event from
 * theme.js). Falls back gracefully if SeaTheme is unavailable.
 */
(function () {
  function urlFor(theme) {
    const variant = theme === 'light' ? 'light_all' : 'dark_all';
    return 'https://{s}.basemaps.cartocdn.com/' + variant + '/{z}/{x}/{y}{r}.png';
  }

  function currentTheme() {
    try {
      return window.SeaTheme ? window.SeaTheme.get() :
        (document.documentElement.getAttribute('data-theme') || 'dark');
    } catch (e) { return 'dark'; }
  }

  function addTo(map, opts) {
    opts = opts || {};
    const layer = L.tileLayer(urlFor(currentTheme()), Object.assign({
      attribution: '&copy; OpenStreetMap &copy; CARTO',
      maxZoom: 18,
    }, opts));
    layer.addTo(map);

    function onTheme(e) {
      const theme = (e && e.detail && e.detail.theme) || currentTheme();
      layer.setUrl(urlFor(theme));
    }
    window.addEventListener('sc:theme-change', onTheme);

    return layer;
  }

  window.SeaTiles = { addTo: addTo, urlFor: urlFor };
})();
