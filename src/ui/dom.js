export const dom = {
  get(target) {
    if (!target) return null;
    if (target instanceof Element || target === document || target === window) return target;
    if (typeof target === "string") return document.getElementById(target) || document.querySelector(target);
    return null;
  },

  q(sel, root = document) {
    return (root ?? document).querySelector(sel);
  },

  qa(sel, root = document) {
    return Array.from((root ?? document).querySelectorAll(sel));
  },

  on(target, event, selectorOrHandler, maybeHandler, opts) {
    const el = dom.get(target);
    if (!el) return () => {};

    let selector = null;
    let handler = null;
    if (typeof selectorOrHandler === "function") {
      handler = selectorOrHandler;
    } else {
      selector = selectorOrHandler;
      handler = maybeHandler;
    }

    const wrapped = selector
      ? (e) => {
          const t = e.target?.closest?.(selector);
          if (t && el.contains(t)) handler?.(e, t);
        }
      : (e) => handler?.(e);

    el.addEventListener(event, wrapped, opts);
    return () => {
      try { el.removeEventListener(event, wrapped, opts); } catch {}
    };
  },

  show(target) { const el = dom.get(target); if (el) el.style.display = ""; return el; },
  hide(target) { const el = dom.get(target); if (el) el.style.display = "none"; return el; },
  toggle(target, v) { return (v ? dom.show(target) : dom.hide(target)); },

  setText(target, text) {
    const el = dom.get(target);
    if (!el) return null;
    el.textContent = text ?? "";
    return el;
  },

  getText(target) {
    const el = dom.get(target);
    return el ? el.textContent : null;
  },

  // IMPORTANT: only use with trusted HTML
  setHtml(target, html) {
    const el = dom.get(target);
    if (!el) return null;
    el.innerHTML = html ?? "";
    return el;
  },

  htmlToNode(html) {
    if (typeof html !== "string") return html;
    const t = document.createElement("template");
    t.innerHTML = html;
    const c = t.content;
    if (c.childNodes.length === 1) return c.firstChild;
    return c; // DocumentFragment
  },
};

export class EventRegistry {
  constructor() {
    this._owned = [];
  }

  own(disposer) {
    if (typeof disposer === "function") this._owned.push(disposer);
    return disposer;
  }

  destroy() {
    for (const off of this._owned.splice(0)) {
      try { off(); } catch {}
    }
  }
}
