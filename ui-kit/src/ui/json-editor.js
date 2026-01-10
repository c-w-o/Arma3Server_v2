import { BaseElement } from "./base.js";
import { makeValidator } from "./validation.js";
import { ui } from "./ui.js";

export class JsonTextEditor extends BaseElement {
  constructor({ schema, initialValue = {}, onChange } = {}) {
    super("div");

    this.validator = makeValidator(schema);
    this.onChangeCb = onChange;
    this.onValidCb = null;

    this.text = ui.textarea().el;
    this.text.classList.add("ui-textarea");
    
    this.msg = ui.div().el;
    this.msg.className = "ui-help";

    this.el.append(this.text, this.msg);
    this.setValue(initialValue);

    const handler = () => this._update();
    this.text.addEventListener("input", handler);
    this.own(() => this.text.removeEventListener("input", handler));
  }

  setValue(obj) {
    this.text.value = JSON.stringify(obj, null, 2);
    this._update();
  }

  onValid(fn) {
    this.onValidCb = fn;
    return this;
  }

  _update() {
    let data;
    try {
      data = JSON.parse(this.text.value);
    } catch (e) {
      this.text.classList.add("invalid");
      this.msg.className = "ui-help error";
      this.msg.textContent = "JSON parse error";
      return;
    }

    const res = this.validator(data);
    if (res.ok) {
      this.text.classList.remove("invalid");
      this.msg.className = "ui-help";
      this.msg.textContent = "✓ valid";
      this.onValidCb?.(data);
    } else {
      this.text.classList.add("invalid");
      this.msg.className = "ui-help error";
      const items = (res.errors || []).map(e => `${e.instancePath ?? ""} ${e.message ?? ""}`.trim());
      const box = ui.vdiv().add(
        ui.text("Schema error"),
        ui.ul(items).cls("ui-error-list").left()
      );
      this.msg.replaceChildren(box.el);
    }

    this.onChangeCb?.(data, res);
  }
}