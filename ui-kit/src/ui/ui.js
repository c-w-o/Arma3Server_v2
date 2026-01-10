import { dom } from "./dom.js";

class UINode {
  constructor(el) {
    this.el = el;
    this._owned = [];
    this._children = [];
  }

  // --- composition
  add(...children) {
    const flat = children.flat(Infinity);
    for (const ch of flat) {
      if (ch == null) continue;
      const node = ch?.el ?? ch;
      if (node instanceof Node) {
        this.el.appendChild(node);
      } else {
        this.el.appendChild(document.createTextNode(String(node)));
      }
      if (ch?.destroy) this._children.push(ch);
    }
    return this;
  }

  clear() {
    this.el.replaceChildren();
    return this;
  }

  replace(...children) {
    this.clear();
    return this.add(...children);
  }

  appendTo(parent) {
    const p = dom.get(parent) ?? parent?.el ?? parent;
    (p ?? document.body).appendChild(this.el);
    return this;
  }

  // --- lifecycle-ish cleanup (for glue code)
  own(disposer) {
    if (typeof disposer === "function") this._owned.push(disposer);
    return disposer;
  }

  destroy({ remove = false } = {}) {
    for (const ch of this._children.splice(0)) {
      try { ch.destroy({ remove: true }); } catch {}
    }
    for (const off of this._owned.splice(0)) {
      try { off(); } catch {}
    }
    if (remove && this.el?.parentNode) this.el.parentNode.removeChild(this.el);
  }

  // --- attributes / style
  id(v) { this.el.id = v; return this; }
  cls(...names) {
    const flat = names.flat(Infinity).filter(Boolean);
    if (flat.length) this.el.classList.add(...flat);
    return this;
  }
  attr(k, v) {
    if (v == null) this.el.removeAttribute(k);
    else this.el.setAttribute(k, String(v));
    return this;
  }
  style(obj) {
    for (const [k, v] of Object.entries(obj || {})) this.el.style[k] = v;
    return this;
  }

  // --- intent helpers (python-ish)
  left() { return this.style({ textAlign: "left" }); }
  right() { return this.style({ textAlign: "right" }); }
  center() { return this.style({ textAlign: "center" }); }
  pad(px) { return this.style({ padding: typeof px === "number" ? `${px}px` : px }); }
  gap(px) { return this.style({ gap: typeof px === "number" ? `${px}px` : px }); }

  // --- events (disposer-aware)
  on(evt, handler, opts) {
    return this.own(dom.on(this.el, evt, handler, opts));
  }
  onSel(evt, selector, handler, opts) {
    return this.own(dom.on(this.el, evt, selector, handler, opts));
  }

  // --- text helpers
  text(v) {
    if (v === undefined) return this.el.textContent;
    this.el.textContent = v ?? "";
    return this;
  }

  heading(level = 3) {
    const n = Math.max(1, Math.min(6, level | 0));
    if (this.el.tagName === `H${n}`) return this;
    const h = document.createElement(`h${n}`);
    h.className = this.el.className;
    h.setAttribute("style", this.el.getAttribute("style") || "");
    h.replaceChildren(...this.el.childNodes);
    this.el.replaceWith(h);
    this.el = h;
    return this;
  }
}

// thin wrapper to keep all DOM creation inside this module
function node(tag) {
  return new UINode(document.createElement(tag));
}

export const ui = {
  // query helpers
  q(sel, root = document) { return typeof sel === "string" ? (root ?? document).querySelector(sel) : sel ?? null; },
  qa(sel, root = document) { return Array.from((root ?? document).querySelectorAll(sel)); },

  mount(target, ...children) {
    const root = dom.get(target) ?? target?.el ?? target;
    if (!root) return null;
    const nodes = children.flat(Infinity).filter(x => x != null).map(x => x?.el ?? x);
    root.replaceChildren(...nodes);
    return root;
  },

  // event helper returning disposer (glue code)
  on(target, evt, selectorOrHandler, handler, opts) {
    const el = typeof target === "string" ? document.querySelector(target) : target;
    return dom.on(el, evt, selectorOrHandler, handler, opts);
  },

  // generic tag factory (escape hatch)
  node,

  // common primitives
  div() { return node("div"); },
  span() { return node("span"); },
  text(s = "") { return node("span").text(s); },
  button(label = "OK") { return node("button").attr("type", "button").text(label); },
  input(type = "text") { return node("input").attr("type", type); },
  textarea() { return node("textarea"); },
  select() { return node("select"); },
  option(label = "", value = null) {
    const o = node("option").text(label);
    if (value != null) o.attr("value", value);
    return o;
  },
  img() { return node("img"); },

  // layout helpers
  hdiv() { return node("div").style({ display: "flex", flexDirection: "row", alignItems: "center" }); },
  vdiv() { return node("div").style({ display: "flex", flexDirection: "column" }); },

  // table helpers
  table() { return node("table"); },
  thead() { return node("thead"); },
  tbody() { return node("tbody"); },
  tr() { return node("tr"); },
  th() { return node("th"); },
  td() { return node("td"); },

  // list helpers
  ul(items = []) {
    const ul = node("ul");
    const arr = Array.isArray(items) ? items : [items];
    ul.add(...arr.map(x => ui.li(x)));
    return ul;
  },
  li(x = "") {
    const li = node("li");
    if (x?.el) li.add(x);
    else if (x instanceof Node) li.add(x);
    else li.text(String(x ?? ""));
    return li;
  },
};


/**
 * Store/UI/FSM bindings
 * ---------------------
 * Minimal glue helpers that return disposer() functions.
 */

export function bindText({ target, store, path, format = null, immediate = true }) {
  const el = dom.get(target) ?? target?.el ?? target;
  if (!el) throw new Error("bindText: target not found");
  if (!store?.subscribePath) throw new Error("bindText: store.subscribePath missing");

  const apply = (value) => {
    el.textContent = format ? format(value) : (value ?? "");
  };

  const off = store.subscribePath(path, (value) => apply(value));
  if (immediate) apply(store.getPath(path));
  return off;
}

/**
 * Two-way binding for <input>/<textarea>/<select>
 */
export function bindValue({ target, store, path, event = "input", parse = null, format = null, immediate = true }) {
  const el = dom.get(target) ?? target?.el ?? target;
  if (!el) throw new Error("bindValue: target not found");
  if (!store?.subscribePath) throw new Error("bindValue: store.subscribePath missing");

  const apply = (value) => {
    const v = format ? format(value) : value;
    const next = (v ?? "");
    if (el.value !== String(next)) el.value = String(next);
  };

  const offStore = store.subscribePath(path, (value) => apply(value));
  const offDom = dom.on(el, event, () => {
    const raw = el.value;
    const val = parse ? parse(raw) : raw;
    store.setPath(path, val);
  });

  if (immediate) apply(store.getPath(path));

  return () => {
    try { offDom(); } catch {}
    try { offStore(); } catch {}
  };
}

/**
 * Convenience wrapper: map store changes to FSM events.
 */
export function bindStoreToFsm({ sm, store, path, event, mapPayload = null, immediate = false }) {
  if (!sm?.watchStore) throw new Error("bindStoreToFsm: sm.watchStore missing");
  return sm.watchStore(store, path, event, mapPayload, { immediate });
}