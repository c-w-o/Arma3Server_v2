import { dom } from "./dom.js";
import { ui } from "./ui.js";

export class BaseElement {
  constructor(tag = "div") {
    this.el = ui.node(tag).el;
    this._owned = [];
    this._children = [];
  }

  appendTo(parent) {
    const p = dom.get(parent) ?? parent?.el ?? parent;
    (p ?? document.body).appendChild(this.el);
    return this;
  }

  setText(text) { this.el.textContent = text ?? ""; return this; }

  setStyle(obj) {
    for (const [k, v] of Object.entries(obj || {})) {
      this.el.style[k] = v;
    }
    return this;
  }
  
  initStyle(obj) {
    for (const [k, v] of Object.entries(obj || {})) {
      if (this.el.style[k] === "") this.el.style[k] = v;
    }
    return this;
  }

  addClass(cls) { this.el.classList.add(cls); return this; }

  own(disposer) {
    if (typeof disposer === "function") {
      this._owned.push(disposer);
    }
    return disposer;
  }

  show() { this.el.style.display = ""; return this; }
  hide() { this.el.style.display = "none"; return this; }

  /**
   * Event binding with automatic cleanup.
   *
   * Supported forms:
   *   this.on('click', handler)
   *   this.on('click', '.child', (e, el) => ...)
   *   this.on(otherEl, 'click', handler)
   *   this.on(otherEl, 'click', '.child', handler)
   */
  on(a, b, c, d, e) {
    // overload: (evt, handler) or (evt, selector, handler)
    if (typeof a === "string") {
      return this.own(dom.on(this.el, a, b, c, d));
    }
    // full: (target, evt, ...)
    return this.own(dom.on(a, b, c, d, e));
  }

  add(...children) {
    return this.addTo(this.el, ...children);
  }

  /**
   * Append children into an arbitrary container element while still
   * participating in ownership tracking (destroy() cascades).
   */
  addTo(container, ...children) {
    const target = container?.el ?? container;
    for (const child of children.flat(Infinity)) {
      if (!child) continue;
      const node = child.el ?? child;
      if (node && node.parentNode !== target) target.appendChild(node);
      if (child?.destroy) this._children.push(child);
    }
    return this;
  }

  destroy({ remove = false } = {}) {
    for (const ch of this._children.splice(0)) {
      try { ch.destroy({ remove: true }); } catch {}
    }
    
    for (const off of this._owned.splice(0)) {
      try { off(); } catch {}
    }
    if (remove && this.el?.parentNode) {
      this.el.parentNode.removeChild(this.el);
    }
  }
}