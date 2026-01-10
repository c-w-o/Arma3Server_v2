import { BaseElement } from "./base.js";

/**
 * DialogStack + ModalDialog
 * ------------------------
 * hdjs-inspired modal stacking with focus handling - thanks Dieter
 */

function getFocusable(root) {
  const nodes = root.querySelectorAll('a[href],button,input,textarea,select,[tabindex]:not([tabindex="-1"])');
  const out = [];
  for (const n of nodes) {
    if (!n) continue;
    if (n.disabled) continue;
    // skip "display:none" / detached
    if (n.offsetParent === null && n !== document.activeElement) continue;
    out.push(n);
  }
  return out;
}

export class DialogStack {
  constructor({ baseZ = 1000 } = {}) {
    this.baseZ = baseZ;
    this.stack = [];
    this._z = baseZ;
  }

  top() { return this.stack.length ? this.stack[this.stack.length - 1] : null; }

  push(dialog) {
    if (!dialog) return;
    this.stack.push(dialog);
    this._z += 2;
    dialog._setZ(this._z);
    this._syncVisibility();
  }

  pop(dialog) {
    const idx = this.stack.indexOf(dialog);
    if (idx < 0) return;
    this.stack.splice(idx, 1);
    this._syncVisibility();
  }

  _syncVisibility() {
    const top = this.top();
    for (const d of this.stack) {
      d._setVisible(d === top);
    }
  }
}

export class ModalDialog extends BaseElement {
  constructor(dialogStack, { dismissOnBackdrop = true, dismissOnEsc = true } = {}) {
    super("div");
    this.stack = dialogStack;
    this.dismissOnBackdrop = dismissOnBackdrop;
    this.dismissOnEsc = dismissOnEsc;

    this._shown = false;
    this._restoreFocusEl = null;
    this._contentOwned = [];

    this.el.className = "ui-modal-overlay";
    this.el.setAttribute("role", "dialog");
    this.el.setAttribute("aria-modal", "true");

    this.panel = new BaseElement("div").addClass("ui-modal-panel");
    this.add(this.panel);

    // backdrop click
    this.on("mousedown", (e) => {
      if (!this.dismissOnBackdrop) return;
      if (e.target === this.el) this.close({ reason: "backdrop" });
    });

    this._onKeyUp = this._onKeyUp.bind(this);
    this._onKeyDown = this._onKeyDown.bind(this);
  }

  setContent(nodeOrElement) {
    // Destroy previous tracked content (if any)
    for (const ch of this._contentOwned.splice(0)) {
      try { ch.destroy({ remove: true }); } catch {}
    }

    // Clear DOM (covers raw nodes that don't have destroy())
    this.panel.el.innerHTML = "";

    if (typeof nodeOrElement === "string") {
      this.panel.el.textContent = nodeOrElement;
      return this;
    }

    if (!nodeOrElement) return this;

    // Use panel.add(...) so BaseElement children get tracked properly.
    this.panel.add(nodeOrElement);

    // Additionally track on the modal instance too, so we can destroy content
    // on subsequent setContent() calls (panel.add only guarantees cleanup when
    // the whole dialog is destroyed).
    if (nodeOrElement?.destroy) this._contentOwned.push(nodeOrElement);
    return this;
  }

  _setZ(z) {
    this.el.style.zIndex = String(z);
    this.panel.el.style.zIndex = String(z + 1);
  }

  _setVisible(v) {
    this.el.style.display = v ? "" : "none";
    if (v) {
      // try focus first focusable
      setTimeout(() => {
        const focusables = getFocusable(this.el);
        (focusables[0] ?? this.panel.el)?.focus?.();
      }, 0);
    }
  }

  show() {
    if (this._shown) return this;
    this._shown = true;
    try { this._restoreFocusEl = document.activeElement; } catch { this._restoreFocusEl = null; }

    document.body.appendChild(this.el);
    this.stack.push(this);
    document.addEventListener("keyup", this._onKeyUp);
    document.addEventListener("keydown", this._onKeyDown);
    return this;
  }

  close(evt = { reason: "programmatic" }) {
    if (!this._shown) return;
    this._shown = false;
    document.removeEventListener("keyup", this._onKeyUp);
    document.removeEventListener("keydown", this._onKeyDown);

    this.stack.pop(this);
    this.destroy({ remove: true });

    // Restore focus only if no modal remains
    if (!this.stack.top() && this._restoreFocusEl?.focus) {
      setTimeout(() => { try { this._restoreFocusEl.focus(); } catch {} }, 0);
    }
  }

  _onKeyUp(e) {
    if (!this._shown) return;
    if (this.stack.top() !== this) return;
    if (!this.dismissOnEsc) return;
    if (e.key === "Escape" || e.keyCode === 27) {
      this.close({ reason: "escape" });
    }
  }

  _onKeyDown(e) {
    if (!this._shown) return;
    if (this.stack.top() !== this) return;
    // focus trap on Tab
    if (e.key !== "Tab" && e.keyCode !== 9) return;

    const focusables = getFocusable(this.el);
    if (focusables.length < 1) return;

    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement;

    if (e.shiftKey) {
      if (active === first || active === this.el) {
        last.focus();
        e.preventDefault();
      }
    } else {
      if (active === last) {
        first.focus();
        e.preventDefault();
      }
    }
  }
}