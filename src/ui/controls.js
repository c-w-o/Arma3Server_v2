import { BaseElement } from "./base.js";
import { ui } from "./ui.js";

export class Button extends BaseElement {
  constructor(text, { variant = "primary" } = {}) {
    super("button");
    this.setText(text);
    this.el.type = "button";
    this.el.classList.add("ui-btn");
    this.setVariant(variant);
  }

  setVariant(variant) {
    this.el.classList.remove("primary", "secondary", "danger");
    if (variant && variant !== "primary") this.el.classList.add(variant);
    return this;
  }

  setDisabled(disabled = true) {
    this.el.disabled = !!disabled;
    return this;
  }

  onClick(fn) {
    return this.on("click", fn);
  }
}

export class TextField extends BaseElement {
  constructor(value = "", { type = "text", placeholder = "" } = {}) {
    super("input");
    this.el.type = type;
    this.el.value = value ?? "";
    this.el.placeholder = placeholder;
    this.el.classList.add("ui-input");
  }

  getValue() { return this.el.value; }

  setValue(v) { this.el.value = v ?? ""; return this; }

  setPlaceholder(p) { this.el.placeholder = p ?? ""; return this; }

  setInvalid(invalid = true) {
    this.el.classList.toggle("invalid", !!invalid);
    return this;
  }
  
  // in TextField class:
  bind(store, path) {
    // init
    this.el.value = store.getPath(path) ?? "";
  
    // UI -> Store
    this.on("input", () => store.setPath(path, this.getValue()));
  
    // Store -> UI
    this.own(store.subscribePath(path, (val) => this.setValue(val)));

    return this;
  }
}

export class Checkbox extends BaseElement {
  /**
   * A styled checkbox wrapper. Without CSS it is still usable and aligned.
   *
   * Options:
   * - label: text shown next to checkbox/slider
   * - slider: render as switch slider (CSS-enhanced)
   * - checked: initial state (or pass as first arg like before)
   */
  constructor(checked = false, { label = "", slider = false } = {}) {
    // We render a wrapper <label> so the whole row is clickable.
    super("label");
    this.el.classList.add("ui-check");

    // Minimal fallback styling (CSS can override)
    this.initStyle({
      display: "inline-flex",
    });

    // Real checkbox input
    this.input = ui.input("checkbox").el;
    this.input.checked = !!checked;

    this.textEl = ui.span().el;
    this.textEl.classList.add("ui-checkbox-text");
    this.textEl.textContent = label;

    // Optional slider track (CSS-enhanced)
    this.sliderEl = null;
    this.switchBox = null;
    
    if (slider) {
      // IMPORTANT:
      // .ui-switch in ui-kit-0.css is a fixed-size switch box (44x24).
      // Therefore it must NOT be on the outer <label>. Put it on an inner element.
      this.switchBox = ui.span().el;
      this.switchBox.className = "ui-switch";
    
      this.sliderEl = ui.span().el;
      this.sliderEl.className = "ui-slider";
    
      // switchBox contains only input + slider visuals
      this.switchBox.append(this.input, this.sliderEl);
      
      // outer label contains switchBox + text
      this.el.append(this.switchBox, this.textEl);
    } else {
      // Classic checkbox: input + text
      this.el.append(this.input, this.textEl);
    }
  }

  setLabel(text) {
    this.textEl.textContent = text ?? "";
    return this;
  }

  getValue() {
    return !!this.input.checked;
  }

  setValue(v) {
    this.input.checked = !!v;
    return this;
  }

  /**
   * Override event binding to attach to the real input for change/input events.
   * All listeners are owned and removed on destroy().
   */
  on(event, handler, options) {
    const target = this.input;
    target.addEventListener(event, handler, options);
    this.own(() => target.removeEventListener(event, handler, options));
    return this;
  }

  bind(store, path) {
    // init
    this.setValue(store.getPath(path) ?? false);

    // UI -> Store
    this.on("change", () => store.setPath(path, this.getValue()));

    // Store -> UI
    this.own(store.subscribePath(path, (val) => {
      const next = !!val;
      if (this.getValue() !== next) this.setValue(next);
    }));

    return this;
  }
}

export class Select extends BaseElement {
  constructor({
    options = [],
    value,
    parse = (s) => s,
    format = (v) => (v ?? "") === "" ? "" : String(v),
    placeholder = null, // z.B. "Bitte wählen…"
  } = {}) {
    super("select");
    this.el.classList.add("ui-select");

    this._parse = parse;
    this._format = format;

    this.setOptions(options, { placeholder });

    if (value !== undefined) this.el.value = this._format(value);
  }

  setOptions(options = [], { placeholder = null } = {}) {
    this.el.innerHTML = "";

    if (placeholder != null) {
      const o = ui.option(String(placeholder), "").el;
      o.value = "";
      o.textContent = String(placeholder);
      this.el.appendChild(o);
    }

    for (const opt of options) {
      const value = (opt && typeof opt === "object") ? opt.value : opt;
      const label = (opt && typeof opt === "object") ? (opt.label ?? opt.value) : opt;

      const o = ui.option(label, value).el;
      o.value = String(value);
      o.textContent = String(label);
      this.el.appendChild(o);
    }
    return this;
  }

  getValue() { return this.el.value; }

  getTypedValue() { return this._parse(this.getValue()); }

  setValue(v) { this.el.value = this._format(v); return this; }

  setInvalid(invalid = true) {
    this.el.classList.toggle("invalid", !!invalid);
    return this;
  }

  bind(store, path) {
    // init (Store -> UI)
    this.setValue(store.getPath(path));

    // UI -> Store
    this.on("change", () => store.setPath(path, this.getTypedValue()));

    // Store -> UI
    this.own(store.subscribePath(path, (val) => this.setValue(val)));

    return this;
  }
}

// --- Simple text blocks --------------------------------------

// Generic text container (div by default)
export class UIKText extends BaseElement {
  constructor(text = "", { tag = "div", muted = false, className = "" } = {}) {
    super(tag);
    if (className) this.el.className = className;
    if (muted) this.el.classList.add("muted");
    this.setText(text);
  }
}
export { UIKText as Text };

export class Label extends UIKText {
  constructor(text = "") {
    super(text, { tag: "div", className: "ui-label" });
  }
}

export class Heading extends BaseElement {
  constructor(text = "", { level = 2 } = {}) {
    super(`h${Math.min(6, Math.max(1, level))}`);
    this.el.style.margin = "0";
    this.setText(text);
  }
}

export class Pre extends BaseElement {
  constructor(text = "") {
    super("pre");
    this.el.style.margin = "0";
    this.el.style.whiteSpace = "pre-wrap";
    this.setText(text);
  }
}