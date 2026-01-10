import { ui } from "./ui.js";

import { BaseElement } from "./base.js";
import { VDiv } from "./layout.js";
import { SelectionGroup } from "./selection.js";

export class Tabs extends BaseElement {
  constructor({ active = null, className = "" } = {}) {
    super("div");
    this.el.className = `ui-tabs ${className}`.trim();

    this.active = active;
    this.tabs = []; // {id, title, panel, factory, built}

    this.onChangeCb = null;

    // Button-based selection (tab bar)
    this.group = new SelectionGroup({
      active: this.active,
      wrap: false, // important for detecting overflow
      className: "ui-tabbar"
    });

    // ARIA: a tablist
    this.group.bar.el.setAttribute("role", "tablist");

    this.group.onChange((id) => {
      this.active = id;
      this._applyActive();
      this.onChangeCb?.(id);
      this._syncDropdown();
    });

    // Dropdown (responsive fallback)
    this.dropdown = ui.select().el;
    this.dropdown.className = "ui-tabselect";
    
    // Register dropdown handler with cleanup (via BaseElement + dom.on disposer)
    this.on(this.dropdown, "change", () => this.setActive(this.dropdown.value));
    
    // Panels container (owned child)
    this.panels = new VDiv({ className: "ui-tabpanels" });

    // (SelectionGroup has listeners; panels may have future resources)
    this.add(this.group);                 // instead of appendChild(this.group.el)
    this.el.appendChild(this.dropdown);   // dropdown is a raw element, so keep it as-is
    this.add(this.panels);                // instead of appendChild(this.panels.el)

  }
  
  destroy(opts = { remove: true }) {
    super.destroy(opts);
  }
  onChange(fn) {
    this.onChangeCb = fn;
    return this;
  }

  addTab(id, title, content) {
    // content can be: BaseElement | Node | () => BaseElement/Node
    const factory = (typeof content === "function") ? content : () => content;

    const panel = ui.div().el;
    panel.className = "ui-tabpanel";
    panel.setAttribute("role", "tabpanel");

    // Store tab metadata
    this.tabs.push({ id, title, panel, factory, built: false });

    // Add button to selection group
    this.group.addItem(id, title);

    // Add option to dropdown
    const opt = ui.option(title, id).el;
    opt.value = id;
    opt.textContent = title;
    this.dropdown.appendChild(opt);

    // Append panel container
    this.panels.el.appendChild(panel);

    // Default active if not set
    if (this.active == null) this.active = id;
    this.group.setActive(this.active);
    this._applyActive();
    this._syncDropdown();
    this._updateResponsiveMode();

    return this;
  }

  setActive(id) {
    this.active = id;
    this.group.setActive(id, { focus: true });
    // group.onChange will call _applyActive + sync dropdown
    return this;
  }

  _ensureBuilt(tab) {
    if (tab.built) return;
    const child = tab.factory();
    if (child) tab.panel.appendChild(child.el ?? child);
    tab.built = true;
  }

  _applyActive() {
    for (const t of this.tabs) {
      const isOn = t.id === this.active;

      // Lazy-build panels on first activation (optional but useful)
      if (isOn) this._ensureBuilt(t);

      t.panel.style.display = isOn ? "" : "none";
    }
  }

  _syncDropdown() {
    if (this.dropdown.value !== String(this.active)) {
      this.dropdown.value = String(this.active);
    }
  }

  _updateResponsiveMode() {
    // If tab bar overflows horizontally, switch to dropdown mode
    const bar = this.group.bar.el;

    // scrollWidth > clientWidth => overflow
    const overflow = bar.scrollWidth > bar.clientWidth + 1;

    this.el.classList.toggle("dropdown-mode", overflow);

    // In dropdown mode, hide bar and show select via CSS
  }
}