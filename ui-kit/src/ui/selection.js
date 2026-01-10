// src/ui/selection.js
import { BaseElement } from "./base.js";
import { HDiv } from "./layout.js";
import { Button } from "./controls.js";

export class SelectionGroup extends BaseElement {
  constructor({
    active = null,
    wrap = true,
    variantInactive = "secondary",
    variantActive = "primary",
    className = "",
  } = {}) {
    super("div");
    this.el.className = `ui-selection ${className}`.trim();

    this.active = active;
    this.items = []; // {id, label, btn}
    this.onChangeCb = null;

    this.variantInactive = variantInactive;
    this.variantActive = variantActive;

    // Container for buttons
    this.bar = new HDiv({ gap: 8, wrap, className: "ui-selection-bar" });
    this.add(this.bar); // IMPORTANT: owned child => destroy cascade works

    this.bar.on("keydown", (e) => this._onKeyDown(e));
  }

  onChange(fn) {
    this.onChangeCb = fn;
    return this;
  }

  addItem(id, label) {
    const btn = new Button(label, { variant: this.variantInactive });
    btn.el.classList.add("ui-selection-btn");

    // Make buttons keyboard focusable and expose selection semantics
    btn.el.setAttribute("role", "tab");
    btn.el.setAttribute("aria-selected", "false");

    btn.onClick(() => this.setActive(id, { focus: true }));

    this.bar.add(btn);
    this.items.push({ id, label, btn });

    // Default active if none chosen
    if (this.active == null) this.active = id;

    this._applyActive();
    return this;
  }

  setActive(id, { focus = false } = {}) {
    if (this.active === id) return this;
    this.active = id;
    this._applyActive();

    if (focus) {
      const item = this.items.find((x) => x.id === id);
      item?.btn?.el?.focus();
    }

    this.onChangeCb?.(id);
    return this;
  }

  getActive() {
    return this.active;
  }

  _applyActive() {
    for (const it of this.items) {
      const isOn = it.id === this.active;

      // Toggle styling via button variants
      it.btn.setVariant(isOn ? this.variantActive : this.variantInactive);

      // Also mark active for CSS if needed
      it.btn.el.classList.toggle("active", isOn);

      // ARIA
      it.btn.el.setAttribute("aria-selected", String(isOn));

      // Roving tabindex: only the active one is tab-focusable
      it.btn.el.tabIndex = isOn ? 0 : -1;
    }
  }

  _onKeyDown(e) {
    // Only handle navigation keys when focus is inside the bar
    const keys = ["ArrowLeft", "ArrowRight", "Home", "End", "Enter", " "];
    if (!keys.includes(e.key)) return;

    const ids = this.items.map((x) => x.id);
    const idx = Math.max(0, ids.indexOf(this.active));
    let nextIdx = idx;

    if (e.key === "ArrowLeft") nextIdx = (idx - 1 + ids.length) % ids.length;
    if (e.key === "ArrowRight") nextIdx = (idx + 1) % ids.length;
    if (e.key === "Home") nextIdx = 0;
    if (e.key === "End") nextIdx = ids.length - 1;

    // Activate on Enter/Space, navigate on arrows/home/end
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      this.setActive(this.active, { focus: true });
      return;
    }

    e.preventDefault();
    this.setActive(ids[nextIdx], { focus: true });
  }
}