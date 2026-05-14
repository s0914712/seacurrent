/* SeaCurrent — shared web components.
 * Loaded synchronously in <head> so :not(:defined) hides custom elements until upgrade.
 * No build step. CSS custom properties pierce shadow DOM, so colors_and_type.css tokens apply.
 */

const NAV_LINKS = [
  { id: 'home', href: 'index.html', label: '首頁', en: 'Home' },
  { id: 'app', href: 'app.html', label: '模擬', en: 'Simulator' },
  { id: 'forecast', href: 'forecast.html', label: '預報圖', en: 'Forecast' },
  { id: 'tide', href: 'tide.html', label: '潮汐', en: 'Tide' },
];

const BRAND_SVG = `
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
       stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M2 12c2-2 4-2 6 0s4 2 6 0 4-2 6 0M2 17c2-2 4-2 6 0s4 2 6 0 4-2 6 0M2 7c2-2 4-2 6 0s4 2 6 0 4-2 6 0"/>
  </svg>`;

/* ====================================================================== *
 * <sea-header current-page="forecast" variant="topbar|floating">
 * Renders consistent global nav. Skips render in iframe embed mode.
 * ====================================================================== */
class SeaHeader extends HTMLElement {
  static get observedAttributes() { return ['current-page', 'variant']; }

  connectedCallback() {
    if (this._mounted) return;
    this._mounted = true;

    if (/[?&]embed=1\b/.test(window.location.search)) {
      this.style.display = 'none';
      return;
    }

    const root = this.attachShadow({ mode: 'open' });
    root.innerHTML = this._template();
    this._wire(root);
  }

  attributeChangedCallback() {
    if (!this.shadowRoot) return;
    this.shadowRoot.innerHTML = this._template();
    this._wire(this.shadowRoot);
  }

  _template() {
    const current = this.getAttribute('current-page') || '';
    const variant = this.getAttribute('variant') || 'topbar';
    const items = NAV_LINKS.map(l => `
      <a href="${l.href}" class="link${l.id === current ? ' active' : ''}"
         ${l.id === current ? 'aria-current="page"' : ''}>
        <span class="zh">${l.label}</span>
        <span class="en">${l.en}</span>
      </a>
    `).join('');

    return `
      <style>
        :host {
          display: block;
          font-family: var(--font-sans, sans-serif);
          color: var(--fg-1, #fff);
          --bar-bg: var(--overlay-bg, rgba(16,29,51,0.92));
          /* Establish a stacking context so the mobile drawer (position:absolute
             inside the shadow tree) anchors below the bar and paints above
             Leaflet panes (z-index ~600) instead of falling to the viewport
             bottom and getting covered by the map. */
          position: relative;
          z-index: 1000;
        }
        :host([variant="floating"]) { position: sticky; top: 0; }

        .bar {
          display: flex;
          align-items: center;
          gap: 1rem;
          padding: 0.6rem 1rem;
          background: var(--bar-bg);
          border-bottom: 1px solid var(--border, #1e3050);
          backdrop-filter: var(--overlay-blur, blur(8px));
          min-height: 52px;
        }
        .brand {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          font-weight: 700;
          color: var(--fg-0, #fff);
          text-decoration: none;
          letter-spacing: -0.01em;
          font-size: 1rem;
        }
        .brand svg { width: 22px; height: 22px; }

        nav {
          display: flex;
          align-items: center;
          gap: 0.25rem;
          margin-left: auto;
        }
        .link {
          color: var(--fg-0, #ffffff);
          text-decoration: none;
          padding: 0.45rem 0.75rem;
          border-radius: var(--r-sm, 6px);
          font-size: 0.95em;
          font-weight: 500;
          transition: background var(--dur-fast, 0.15s) var(--ease, ease),
                      color var(--dur-fast, 0.15s) var(--ease, ease);
          display: inline-flex;
          align-items: center;
          gap: 0.4em;
        }
        .link .en { display: none; color: var(--fg-2, #e1e7ef); font-size: 0.85em; }
        .link:hover, .link:focus-visible {
          color: var(--fg-0, #fff);
          background: rgba(74, 158, 255, 0.10);
          outline: none;
        }
        .link:focus-visible { box-shadow: var(--focus-ring, 0 0 0 3px rgba(74,158,255,0.6)); }
        .link.active {
          color: var(--accent, #4a9eff);
          background: rgba(74, 158, 255, 0.12);
        }

        .menu-btn {
          display: none;
          margin-left: auto;
          background: transparent;
          border: 1px solid var(--border, #1e3050);
          color: var(--fg-1, #fff);
          padding: 0.45rem 0.7rem;
          border-radius: var(--r-sm, 6px);
          cursor: pointer;
          font-size: 1.1em;
        }
        .menu-btn:focus-visible { box-shadow: var(--focus-ring, 0 0 0 3px rgba(74,158,255,0.6)); outline: none; }

        .theme-btn {
          background: transparent;
          border: 1px solid var(--border, #1e3050);
          color: var(--fg-1, #fff);
          padding: 0.4rem 0.55rem;
          border-radius: var(--r-sm, 6px);
          cursor: pointer;
          font-size: 1em;
          line-height: 1;
        }
        .theme-btn:hover { background: rgba(74,158,255,0.10); }
        .theme-btn:focus-visible { box-shadow: var(--focus-ring, 0 0 0 3px rgba(74,158,255,0.6)); outline: none; }

        @media (min-width: 1024px) {
          .link .en { display: inline; }
        }

        /* Mobile drawer — covers the 700–900px gap that the old nav left open */
        @media (max-width: 768px) {
          nav {
            position: absolute;
            top: 100%;
            right: 0.5rem;
            left: 0.5rem;
            flex-direction: column;
            align-items: stretch;
            background: var(--bg-elevated, #1a3558);
            border: 1px solid var(--border, #1e3050);
            border-radius: var(--r-md, 8px);
            padding: 0.4rem;
            box-shadow: var(--shadow-2, 0 4px 14px rgba(0,0,0,0.35));
            display: none;
          }
          nav.open { display: flex; }
          .menu-btn { display: inline-flex; }
          .link { padding: 0.7rem 0.8rem; }
        }
      </style>
      <header class="bar" role="banner">
        <a class="brand" href="index.html">${BRAND_SVG}<span>SeaCurrent</span></a>
        <button type="button" class="menu-btn" aria-label="切換選單" aria-expanded="false" aria-controls="seanav">&#9776;</button>
        <nav id="seanav" aria-label="主選單">${items}</nav>
        <button type="button" class="theme-btn" aria-label="切換深淺色主題" title="切換主題">
          <span class="theme-icon" aria-hidden="true">◐</span>
        </button>
      </header>
      <noscript>
        <p style="padding:0.5rem 1rem;background:#1a3558;color:#fff;">
          需 JavaScript 才能顯示完整導覽，請至
          <a href="index.html" style="color:#4a9eff;">首頁</a>。
        </p>
      </noscript>
    `;
  }

  _wire(root) {
    const btn = root.querySelector('.menu-btn');
    const nav = root.querySelector('nav');
    if (btn && nav) {
      btn.addEventListener('click', () => {
        const open = nav.classList.toggle('open');
        btn.setAttribute('aria-expanded', String(open));
      });
      nav.addEventListener('click', e => {
        if (e.target.closest('.link')) {
          nav.classList.remove('open');
          btn.setAttribute('aria-expanded', 'false');
        }
      });
    }

    const themeBtn = root.querySelector('.theme-btn');
    const themeIcon = root.querySelector('.theme-icon');
    const syncIcon = () => {
      if (!themeIcon || !window.SeaTheme) return;
      themeIcon.textContent = window.SeaTheme.get() === 'light' ? '☾' : '☀';
    };
    syncIcon();
    if (themeBtn) {
      themeBtn.addEventListener('click', () => {
        if (window.SeaTheme) window.SeaTheme.toggle();
        syncIcon();
      });
    }
    window.addEventListener('sc:theme-change', syncIcon);
  }
}
customElements.define('sea-header', SeaHeader);

/* ====================================================================== *
 * <sea-tabbar current-page="home|app|forecast|tide">
 * Mobile-only fixed bottom navigation (≤767.98px). Hidden on desktop where
 * <sea-header> takes over. Adds body.has-tabbar so non-:has() browsers can
 * still lift Leaflet attribution out from under it.
 * Fires sc:tabbar-nav { to } on click so pages can intercept (e.g. unsaved
 * form state). Calling event.preventDefault() stops navigation.
 * ====================================================================== */
const TAB_ICONS = {
  home:     '<path d="M3 11l9-8 9 8v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
  app:      '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
  forecast: '<path d="M3 6h18M3 12h18M3 18h12"/><circle cx="19" cy="18" r="2"/>',
  tide:     '<path d="M2 12c2-2 4-2 6 0s4 2 6 0 4-2 6 0M2 18c2-2 4-2 6 0s4 2 6 0 4-2 6 0"/>',
};

class SeaTabbar extends HTMLElement {
  static get observedAttributes() { return ['current-page']; }

  connectedCallback() {
    if (this._mounted) return;
    this._mounted = true;

    if (/[?&]embed=1\b/.test(window.location.search)) {
      this.style.display = 'none';
      return;
    }

    document.body.classList.add('has-tabbar');
    const root = this.attachShadow({ mode: 'open' });
    root.innerHTML = this._template();
    this._wire(root);
  }

  disconnectedCallback() {
    document.body.classList.remove('has-tabbar');
  }

  attributeChangedCallback() {
    if (!this.shadowRoot) return;
    this.shadowRoot.innerHTML = this._template();
    this._wire(this.shadowRoot);
  }

  _template() {
    const current = this.getAttribute('current-page') || '';
    const items = NAV_LINKS.map(l => `
      <a href="${l.href}" class="tab${l.id === current ? ' active' : ''}"
         data-id="${l.id}"
         ${l.id === current ? 'aria-current="page"' : ''}
         aria-label="${l.label} ${l.en}">
        <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
             aria-hidden="true">${TAB_ICONS[l.id] || ''}</svg>
        <span class="lbl">${l.label}</span>
      </a>
    `).join('');

    return `
      <style>
        :host { display: none; font-family: var(--font-sans, sans-serif); }
        @media (max-width: 767.98px) { :host { display: block; } }

        .bar {
          position: fixed;
          bottom: 0; left: 0; right: 0;
          z-index: 1100;
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          background: var(--overlay-bg, rgba(16,29,51,0.92));
          backdrop-filter: var(--overlay-blur, blur(8px));
          -webkit-backdrop-filter: var(--overlay-blur, blur(8px));
          border-top: 1px solid var(--border, #1e3050);
          padding-bottom: env(safe-area-inset-bottom);
          min-height: 56px;
        }
        .tab {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 2px;
          padding: 6px 4px;
          color: var(--fg-2, #c9d2dd);
          text-decoration: none;
          font-size: 0.72em;
          font-weight: 500;
          min-height: 48px;
          transition: color var(--dur-fast, 0.15s) var(--ease, ease),
                      background var(--dur-fast, 0.15s) var(--ease, ease);
        }
        .tab .ico { width: 22px; height: 22px; flex-shrink: 0; }
        .tab .lbl { line-height: 1; }
        .tab:hover, .tab:focus-visible {
          color: var(--fg-0, #fff);
          background: rgba(74, 158, 255, 0.08);
          outline: none;
        }
        .tab:focus-visible { box-shadow: inset 0 0 0 2px var(--accent, #4a9eff); }
        .tab.active { color: var(--accent, #4a9eff); }

        @media (prefers-reduced-motion: reduce) {
          .tab { transition: none; }
        }
      </style>
      <nav class="bar" role="navigation" aria-label="主要分頁">${items}</nav>
    `;
  }

  _wire(root) {
    root.querySelectorAll('.tab').forEach(a => {
      a.addEventListener('click', e => {
        const to = a.dataset.id;
        const evt = new CustomEvent('sc:tabbar-nav', {
          detail: { to, href: a.href },
          bubbles: true, composed: true, cancelable: true,
        });
        this.dispatchEvent(evt);
        if (evt.defaultPrevented) e.preventDefault();
      });
    });
  }
}
customElements.define('sea-tabbar', SeaTabbar);

/* ====================================================================== *
 * <sea-next-step to="app|forecast|tide|home" title="..." body="..."
 *                cta-label="..." variant="primary|ghost">
 * End-of-page CTA card that hands the user to the next likely destination.
 * Resolves `to` against NAV_LINKS so href and labels stay single-sourced.
 * ====================================================================== */
class SeaNextStep extends HTMLElement {
  static get observedAttributes() { return ['to', 'title', 'body', 'cta-label', 'variant']; }

  connectedCallback() {
    if (this._mounted) return;
    this._mounted = true;
    if (/[?&]embed=1\b/.test(window.location.search)) { this.style.display = 'none'; return; }
    const root = this.attachShadow({ mode: 'open' });
    root.innerHTML = this._template();
  }
  attributeChangedCallback() {
    if (!this.shadowRoot) return;
    this.shadowRoot.innerHTML = this._template();
  }
  _template() {
    const to = this.getAttribute('to') || 'home';
    const link = NAV_LINKS.find(l => l.id === to) || NAV_LINKS[0];
    const title = this.getAttribute('title') || `下一步：${link.label}`;
    const body = this.getAttribute('body') || '';
    const cta = this.getAttribute('cta-label') || `${link.label} →`;
    const variant = this.getAttribute('variant') || 'primary';
    return `
      <style>
        :host { display: block; font-family: var(--font-sans, sans-serif); }
        .card {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
          padding: clamp(1rem, 3vw, 1.5rem);
          margin: clamp(1.25rem, 4vw, 2rem) auto;
          max-width: 56rem;
          background: var(--bg-elevated, #1a3558);
          border: 1px solid var(--border, #1e3050);
          border-radius: var(--r-lg, 14px);
          color: var(--fg-1, #e0e6ed);
        }
        :host([variant="ghost"]) .card {
          background: transparent;
          border-style: dashed;
        }
        .eyebrow {
          font-size: 0.78em;
          letter-spacing: 0.06em;
          text-transform: uppercase;
          color: var(--fg-3, #9aa6b4);
          font-weight: 600;
        }
        .title {
          font-size: clamp(1.1em, 2.4vw, 1.35em);
          font-weight: 700;
          color: var(--fg-0, #fff);
          margin: 0;
        }
        .body { font-size: 0.95em; line-height: 1.5; color: var(--fg-2, #c9d2dd); margin: 0; }
        .row {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          margin-top: 0.25rem;
          flex-wrap: wrap;
        }
        .btn {
          display: inline-flex;
          align-items: center;
          gap: 0.4rem;
          padding: 0.65rem 1.1rem;
          min-height: 44px;
          background: var(--accent, #4a9eff);
          color: #fff;
          text-decoration: none;
          font-weight: 600;
          border-radius: var(--r-md, 8px);
          transition: background var(--dur-fast, 0.15s) var(--ease, ease),
                      transform var(--dur-fast, 0.15s) var(--ease, ease);
        }
        .btn:hover { background: var(--accent-strong, #1f7be0); }
        .btn:focus-visible {
          outline: none;
          box-shadow: var(--focus-ring, 0 0 0 3px rgba(74,158,255,0.6));
        }
        .btn .chev { transition: transform var(--dur-fast, 0.15s) var(--ease, ease); }
        .btn:hover .chev { transform: translateX(2px); }
        @media (prefers-reduced-motion: reduce) {
          .btn, .btn .chev { transition: none; }
          .btn:hover .chev { transform: none; }
        }
      </style>
      <section class="card" aria-labelledby="ns-title">
        <span class="eyebrow">下一步 · NEXT</span>
        <h2 id="ns-title" class="title">${title}</h2>
        ${body ? `<p class="body">${body}</p>` : ''}
        <div class="row">
          <a class="btn" href="${link.href}">
            <span>${cta}</span>
            <span class="chev" aria-hidden="true">→</span>
          </a>
        </div>
      </section>
    `;
  }
}
customElements.define('sea-next-step', SeaNextStep);

/* ====================================================================== *
 * <sea-footer>
 * ====================================================================== */
class SeaFooter extends HTMLElement {
  connectedCallback() {
    if (this._mounted) return;
    this._mounted = true;

    if (/[?&]embed=1\b/.test(window.location.search)) {
      this.style.display = 'none';
      return;
    }

    const root = this.attachShadow({ mode: 'open' });
    root.innerHTML = `
      <style>
        :host { display: block; font-family: var(--font-sans, sans-serif); }
        footer {
          padding: 1.25rem 1rem;
          border-top: 1px solid var(--border, #1e3050);
          background: var(--bg-1, #101d33);
          color: var(--fg-1, #f5f7fb);
          font-size: 0.92em;
          display: flex;
          flex-wrap: wrap;
          gap: 0.75rem 1.5rem;
          align-items: center;
          justify-content: space-between;
        }
        .links { display: flex; gap: 1rem; flex-wrap: wrap; }
        a { color: var(--fg-0, #ffffff); text-decoration: none; }
        a:hover, a:focus-visible { color: var(--accent, #4a9eff); outline: none; }
        a:focus-visible { box-shadow: var(--focus-ring, 0 0 0 3px rgba(74,158,255,0.6)); border-radius: var(--r-sm, 6px); }
      </style>
      <footer>
        <span>SeaCurrent · MIT · Data courtesy of Taiwan CWA</span>
        <div class="links">
          <a href="app.html">模擬器</a>
          <a href="forecast.html">預報圖</a>
          <a href="tide.html">潮汐</a>
          <a href="https://github.com/s0914712/seacurrent" target="_blank" rel="noopener">GitHub</a>
        </div>
      </footer>
    `;
  }
}
customElements.define('sea-footer', SeaFooter);

/* ====================================================================== *
 * <sea-toast> — singleton notification queue.
 * Usage: document.querySelector('sea-toast').show({type:'error', msg:'...', retry: fn})
 * If no <sea-toast> exists, one is created on first call via SeaToast.notify().
 * ====================================================================== */
class SeaToast extends HTMLElement {
  connectedCallback() {
    if (this._mounted) return;
    this._mounted = true;
    const root = this.attachShadow({ mode: 'open' });
    root.innerHTML = `
      <style>
        :host {
          position: fixed;
          right: 1rem;
          bottom: 1rem;
          z-index: 9999;
          font-family: var(--font-sans, sans-serif);
          display: flex;
          flex-direction: column-reverse;
          gap: 0.5rem;
          max-width: min(380px, calc(100vw - 2rem));
          pointer-events: none;
        }
        .toast {
          pointer-events: auto;
          background: var(--bg-elevated, #1a3558);
          color: var(--fg-1, #e0e6ed);
          border: 1px solid var(--border, #1e3050);
          border-left: 3px solid var(--accent, #4a9eff);
          padding: 0.75rem 0.9rem;
          border-radius: var(--r-md, 8px);
          box-shadow: var(--shadow-2, 0 4px 14px rgba(0,0,0,0.35));
          display: flex;
          gap: 0.6rem;
          align-items: flex-start;
          animation: in 0.25s var(--ease, ease) both;
        }
        .toast.leaving { animation: out 0.2s var(--ease, ease) both; }
        .toast.success { border-left-color: var(--success, #34d399); background: var(--surface-success, rgba(52,211,153,0.12)); }
        .toast.error   { border-left-color: var(--error, #f87171);   background: var(--surface-error, rgba(248,113,113,0.14)); }
        .toast.warn    { border-left-color: var(--warn, #f59e0b);    background: var(--surface-warn, rgba(245,158,11,0.14)); }
        .icon { font-size: 1.05em; line-height: 1.2; }
        .body { flex: 1; font-size: 0.92em; line-height: 1.45; }
        .body .title { font-weight: 600; color: var(--fg-0, #fff); margin-bottom: 0.2em; }
        .actions { display: flex; gap: 0.4rem; margin-top: 0.5rem; }
        button {
          background: transparent;
          color: var(--fg-1, #e0e6ed);
          border: 1px solid var(--border-strong, #2c4f7a);
          padding: 0.3rem 0.6rem;
          border-radius: var(--r-sm, 6px);
          cursor: pointer;
          font-size: 0.85em;
        }
        button:hover { background: rgba(74,158,255,0.10); }
        button:focus-visible { outline: none; box-shadow: var(--focus-ring, 0 0 0 3px rgba(74,158,255,0.6)); }
        .close {
          background: transparent;
          border: 0;
          color: var(--fg-3, #7a8fa6);
          font-size: 1.1em;
          cursor: pointer;
          padding: 0 0.2rem;
        }
        .close:hover { color: var(--fg-0, #fff); }
        @keyframes in {
          from { transform: translateY(8px); opacity: 0; }
          to   { transform: translateY(0);   opacity: 1; }
        }
        @keyframes out {
          from { transform: translateY(0); opacity: 1; }
          to   { transform: translateY(8px); opacity: 0; }
        }
        @media (prefers-reduced-motion: reduce) {
          .toast, .toast.leaving { animation: none; }
        }
      </style>
      <div id="region" aria-live="polite" aria-atomic="false"></div>
    `;
    this._region = root.getElementById('region');
  }

  /**
   * @param {{type?: 'info'|'success'|'warn'|'error', title?: string, msg: string, ttl?: number, retry?: Function}} opts
   */
  show(opts) {
    const { type = 'info', title, msg, ttl = 5000, retry } = opts || {};
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.setAttribute('role', type === 'error' ? 'alert' : 'status');

    const icon = type === 'success' ? '✔' :
                 type === 'error'   ? '⚠' :
                 type === 'warn'    ? '⚠' : 'i';

    const body = document.createElement('div');
    body.className = 'body';
    if (title) {
      const t = document.createElement('div');
      t.className = 'title';
      t.textContent = title;
      body.appendChild(t);
    }
    const m = document.createElement('div');
    m.textContent = msg;
    body.appendChild(m);

    if (typeof retry === 'function') {
      const actions = document.createElement('div');
      actions.className = 'actions';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = '重試';
      btn.addEventListener('click', () => {
        try { retry(); } finally { dismiss(); }
      });
      actions.appendChild(btn);
      body.appendChild(actions);
    }

    const iconEl = document.createElement('span');
    iconEl.className = 'icon';
    iconEl.textContent = icon;
    iconEl.setAttribute('aria-hidden', 'true');

    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'close';
    close.setAttribute('aria-label', '關閉通知');
    close.textContent = '×';
    close.addEventListener('click', () => dismiss());

    el.append(iconEl, body, close);
    this._region.appendChild(el);

    let timer = null;
    const dismiss = () => {
      if (!el.parentNode) return;
      clearTimeout(timer);
      el.classList.add('leaving');
      setTimeout(() => el.remove(), 220);
    };
    if (ttl > 0 && !retry) timer = setTimeout(dismiss, ttl);
    return dismiss;
  }
}
customElements.define('sea-toast', SeaToast);

/** Static helper: returns the singleton sea-toast, creating one if missing. */
SeaToast.notify = function notify(opts) {
  let host = document.querySelector('sea-toast');
  if (!host) {
    host = document.createElement('sea-toast');
    document.body.appendChild(host);
  }
  // upgrade may not have run yet
  customElements.whenDefined('sea-toast').then(() => host.show(opts));
  return host;
};
window.SeaToast = SeaToast;

/* ====================================================================== *
 * <sea-skeleton width="100%" height="120" radius="8">
 * Visual shimmer placeholder.
 * ====================================================================== */
class SeaSkeleton extends HTMLElement {
  connectedCallback() {
    if (this._mounted) return;
    this._mounted = true;
    const root = this.attachShadow({ mode: 'open' });
    const w = this.getAttribute('width') || '100%';
    const h = this.getAttribute('height') || '1em';
    const r = this.getAttribute('radius') || '6px';
    root.innerHTML = `
      <style>
        :host { display: block; }
        .sk {
          width: ${CSS.escape ? w : w};
          height: ${typeof h === 'string' && /^\d+$/.test(h) ? h + 'px' : h};
          border-radius: ${typeof r === 'string' && /^\d+$/.test(r) ? r + 'px' : r};
          background: linear-gradient(90deg,
            var(--bg-3, #152238) 0%,
            var(--bg-elevated, #1a3558) 50%,
            var(--bg-3, #152238) 100%);
          background-size: 200% 100%;
          animation: sh 1.4s var(--ease, ease) infinite;
        }
        @keyframes sh { from { background-position: 200% 0; } to { background-position: -200% 0; } }
        @media (prefers-reduced-motion: reduce) {
          .sk { animation: none; opacity: 0.7; }
        }
      </style>
      <div class="sk" role="status" aria-label="載入中"></div>
    `;
  }
}
customElements.define('sea-skeleton', SeaSkeleton);

/* ====================================================================== *
 * <sea-onboarding storage-key="sc:seen-tour">
 * Phase 6 fills in the tour content. Leaving stub so element doesn't FOUC.
 * ====================================================================== */
class SeaOnboarding extends HTMLElement {
  connectedCallback() {
    if (this._mounted) return;
    this._mounted = true;
    const key = this.getAttribute('storage-key') || 'sc:seen-tour';
    if (localStorage.getItem(key) === '1') {
      this.style.display = 'none';
      return;
    }
    const steps = JSON.parse(this.getAttribute('steps') || '[]');
    if (!steps.length) { this.style.display = 'none'; return; }
    this._render(steps, key);
  }

  _render(steps, key) {
    const root = this.attachShadow({ mode: 'open' });
    let i = 0;
    root.innerHTML = `
      <style>
        :host { position: fixed; inset: 0; z-index: 9000; font-family: var(--font-sans, sans-serif); }
        .scrim {
          position: absolute; inset: 0;
          background: rgba(10, 22, 40, 0.78);
          backdrop-filter: blur(2px);
        }
        .card {
          position: absolute;
          left: 50%; top: 50%;
          transform: translate(-50%, -50%);
          background: var(--bg-elevated, #1a3558);
          color: var(--fg-1, #e0e6ed);
          border: 1px solid var(--border, #1e3050);
          border-radius: var(--r-lg, 10px);
          padding: 1.25rem 1.4rem;
          width: min(420px, calc(100vw - 2rem));
          box-shadow: var(--shadow-3, 0 12px 32px rgba(0,0,0,0.45));
        }
        h3 { margin: 0 0 0.4em; color: var(--fg-0, #fff); font-size: 1.1em; }
        p { margin: 0 0 0.8em; color: var(--fg-2, #a9b8cf); line-height: 1.55; font-size: 0.95em; }
        .row { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-top: 0.8em; }
        .dots { display: flex; gap: 0.3rem; }
        .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--border-strong, #2c4f7a); }
        .dot.active { background: var(--accent, #4a9eff); }
        .actions { display: flex; gap: 0.5rem; }
        button {
          padding: 0.45rem 0.9rem;
          border-radius: var(--r-sm, 6px);
          border: 1px solid var(--border-strong, #2c4f7a);
          background: transparent;
          color: var(--fg-1, #e0e6ed);
          cursor: pointer;
          font-size: 0.92em;
        }
        button.primary {
          background: var(--accent-strong, #2563eb);
          border-color: var(--accent-strong, #2563eb);
          color: #fff;
        }
        button:focus-visible { outline: none; box-shadow: var(--focus-ring, 0 0 0 3px rgba(74,158,255,0.6)); }
      </style>
      <div class="scrim"></div>
      <div class="card" role="dialog" aria-modal="true" aria-labelledby="ob-title">
        <h3 id="ob-title"></h3>
        <p id="ob-body"></p>
        <div class="row">
          <div class="dots" id="dots"></div>
          <div class="actions">
            <button type="button" id="skip">略過</button>
            <button type="button" class="primary" id="next">下一步</button>
          </div>
        </div>
      </div>
    `;
    const dots = root.getElementById('dots');
    steps.forEach(() => { const d = document.createElement('span'); d.className = 'dot'; dots.appendChild(d); });
    const update = () => {
      root.getElementById('ob-title').textContent = steps[i].title || '';
      root.getElementById('ob-body').textContent = steps[i].body || '';
      [...dots.children].forEach((d, idx) => d.classList.toggle('active', idx === i));
      root.getElementById('next').textContent = i === steps.length - 1 ? '完成' : '下一步';
    };
    const close = () => {
      localStorage.setItem(key, '1');
      this.remove();
    };
    root.getElementById('skip').addEventListener('click', close);
    root.getElementById('next').addEventListener('click', () => {
      if (i === steps.length - 1) close();
      else { i++; update(); }
    });
    update();
  }
}
customElements.define('sea-onboarding', SeaOnboarding);

/* ====================================================================== *
 * <sea-glossary term="leeway">Leeway</sea-glossary>
 * Term is rendered as an underlined inline trigger. Click/focus shows popover
 * with definition fetched from /assets/glossary.json (cached on first load).
 * ====================================================================== */
let _glossaryCache = null;
async function loadGlossary() {
  if (_glossaryCache) return _glossaryCache;
  try {
    const r = await fetch('assets/glossary.json', { cache: 'force-cache' });
    _glossaryCache = await r.json();
  } catch {
    _glossaryCache = {};
  }
  return _glossaryCache;
}

class SeaGlossary extends HTMLElement {
  connectedCallback() {
    if (this._mounted) return;
    this._mounted = true;
    const root = this.attachShadow({ mode: 'open' });
    const term = (this.getAttribute('term') || '').toLowerCase();
    root.innerHTML = `
      <style>
        :host { display: inline; }
        .trigger {
          color: inherit;
          background: transparent;
          border: 0;
          padding: 0;
          font: inherit;
          cursor: help;
          border-bottom: 1px dotted var(--accent, #4a9eff);
          line-height: inherit;
        }
        .trigger:focus-visible { outline: none; box-shadow: var(--focus-ring, 0 0 0 3px rgba(74,158,255,0.6)); border-radius: 2px; }
        .pop {
          position: absolute;
          z-index: 800;
          max-width: 280px;
          padding: 0.7rem 0.85rem;
          background: var(--bg-elevated, #1a3558);
          color: var(--fg-1, #e0e6ed);
          border: 1px solid var(--border, #1e3050);
          border-radius: var(--r-md, 8px);
          box-shadow: var(--shadow-2, 0 4px 14px rgba(0,0,0,0.35));
          font-size: 0.88em;
          line-height: 1.5;
          display: none;
        }
        .pop.open { display: block; }
        .pop strong { color: var(--fg-0, #fff); display: block; margin-bottom: 0.25em; }
      </style>
      <button type="button" class="trigger" aria-haspopup="dialog">
        <slot></slot>
      </button>
      <span class="pop" role="dialog"></span>
    `;
    const trigger = root.querySelector('.trigger');
    const pop = root.querySelector('.pop');

    const open = async () => {
      const dict = await loadGlossary();
      const entry = dict[term];
      if (!entry) return;
      pop.innerHTML = `<strong>${entry.title || term}</strong>${entry.body || ''}`;
      pop.classList.add('open');
      const r = trigger.getBoundingClientRect();
      pop.style.left = (r.left + window.scrollX) + 'px';
      pop.style.top = (r.bottom + window.scrollY + 6) + 'px';
    };
    const close = () => pop.classList.remove('open');

    trigger.addEventListener('click', () => pop.classList.contains('open') ? close() : open());
    trigger.addEventListener('focus', open);
    trigger.addEventListener('blur', close);
    trigger.addEventListener('keydown', e => { if (e.key === 'Escape') { close(); trigger.blur(); } });
  }
}
customElements.define('sea-glossary', SeaGlossary);
