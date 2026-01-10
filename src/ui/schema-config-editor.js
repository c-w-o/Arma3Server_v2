import { BaseElement } from "./base.js";
import { Tabs } from "./tabs.js";
import { Card, HDiv, VDiv } from "./layout.js";
import { Button, Text } from "./controls.js";
import { makeValidator } from "./validation.js";
import { ui } from "./ui.js";
function deps() {
  return {
    ajv: !!(window.ajv7 || window.Ajv),
    ace: !!window.ace,
    jsonEditor: !!window.JSONEditor,
  };
}
/**
 * SchemaConfigEditor
 * - User: json-editor (visual, supports oneOf/anyOf)
 * - Expert: Ace (raw JSON for value + schema)
 * - AJV is the single gatekeeper: store only updates when valid
 *
 * Expected globals:
 *   - window.JSONEditor  (from json-editor)
 *   - window.ace         (from Ace)
 */
export class SchemaConfigEditor extends BaseElement {
  constructor({
    store,
    valuePath = "jsonConfig",
    schemaPath = null,              // if provided: schema editable in Expert tab
    schema,                         // required if schemaPath not used
    title = "Config Editor",
    allowUserWriteback = true,      // allow json-editor to write to store (valid-only)
    userWritebackDebounceMs = 200,
  } = {}) {
    super("div");
    if (!store) throw new Error("SchemaConfigEditor: store required");
    if (!schema && !schemaPath) throw new Error("SchemaConfigEditor: schema or schemaPath required");

    this.store = store;
    this.valuePath = valuePath;
    this.schemaPath = schemaPath;
    this.allowUserWriteback = allowUserWriteback;

    this._guardFromStore = 0;   // reentrancy guard
    this._guardFromUser = 0;

    // Resolve initial schema
    this.schema = schemaPath ? (store.getPath(schemaPath) ?? {}) : schema;

    // AJV validator (can be Draft-07 or 2020 depending on your makeValidator + loaded Ajv bundle)
    this._compileValidator();

    // ---- UI
    const root = new VDiv({ gap: 12 }).appendTo(this);

    new Text(title, { muted: true }).appendTo(root);

    const d = deps();

    // Tabs always exist
    this.tabs = new Tabs({ active: d.jsonEditor ? "user" : "expert" }).appendTo(root);
    
    // User tab: only if JSONEditor is present
    if (d.jsonEditor) {
      this.tabs.addTab("user", "User UI", () => this._buildUserTab({ debounceMs: userWritebackDebounceMs }));
    } else {
      this.tabs.addTab("user", "User UI", () => this._buildMissingUserTab());
    }

// Expert tab: prefer Ace, fallback to textarea if Ace missing
this.tabs.addTab("expert", "Expert", () => (d.ace ? this._buildExpertTab() : this._buildExpertFallbackTab()));
    // Keep editors in sync with store
    this.own(store.subscribePath(this.valuePath, () => this._onStoreValueChanged()));
    if (this.schemaPath) this.own(store.subscribePath(this.schemaPath, () => this._onStoreSchemaChanged()));

    // Initial sync
    this._onStoreSchemaChanged();
    this._onStoreValueChanged();
  }
  
  _buildMissingUserTab() {
    const root = new VDiv({ gap: 12 });
    root.add(new Text("json-editor is not loaded (window.JSONEditor missing).", { muted: true }));
    root.add(new Text("Fallback: use Expert tab (raw JSON).", { muted: true }));
    return root;
  }
  
  _buildExpertFallbackTab() {
    const root = new VDiv({ gap: 12 });
  
    root.add(new Text("Ace is not loaded (window.ace missing).", { muted: true }));
    root.add(new Text("Fallback: plain textarea editing (no syntax highlight).", { muted: true }));
  
    const cardVal = new Card({ title: "Value JSON (fallback)" }).appendTo(root);
    const taVal = ui.textarea().el;
    taVal.className = "ui-textarea expert";
    cardVal.el.appendChild(taVal);
  
    const cardSchema = new Card({ title: this.schemaPath ? "Schema JSON (fallback)" : "Schema JSON (read-only fallback)" }).appendTo(root);
    const taSchema = ui.textarea().el;
    taSchema.className = "ui-textarea expert";
    taSchema.readOnly = !this.schemaPath;
    cardSchema.el.appendChild(taSchema);
  
    const actions = new HDiv({ gap: 8, wrap: true }).appendTo(root);
    new Button("Format value", { variant: "secondary" }).appendTo(actions).onClick(() => formatTextareaJson(taVal));
    new Button("Apply value").appendTo(actions).onClick(() => {
      const parsed = safeParse(taVal.value);
      if (!parsed.ok) return alert(`Value parse error: ${parsed.error}`);
      const res = this._validate(parsed.obj);
      if (!res.ok) return alert(`Value invalid (${res.errors.length} errors)`);
      this._setValueToStore(parsed.obj);
    });
  
    if (this.schemaPath) {
      new Button("Format schema", { variant: "secondary" }).appendTo(actions).onClick(() => formatTextareaJson(taSchema));
      new Button("Apply schema").appendTo(actions).onClick(() => {
        const parsed = safeParse(taSchema.value);
        if (!parsed.ok) return alert(`Schema parse error: ${parsed.error}`);
        // try compile
        try {
          this.schema = parsed.obj;
          this._compileValidator();
        } catch (e) {
          return alert(`Schema compile error: ${String(e?.message || e)}`);
        }
        this._setSchemaToStore(parsed.obj);
      });
    }
  
    // sync initial
    taVal.value = JSON.stringify(this._getValueFromStore() ?? {}, null, 2);
    taSchema.value = JSON.stringify(this._getSchemaFromStore() ?? {}, null, 2);
  
    // sync store → textareas (avoid cursor jumps: only update if equal after trim optional)
    root.own(this.store.subscribePath(this.valuePath, () => {
      const canon = JSON.stringify(this._getValueFromStore() ?? {}, null, 2);
      if (taVal.value.trim() === canon.trim()) return;
      taVal.value = canon;
    }));
    if (this.schemaPath) {
      root.own(this.store.subscribePath(this.schemaPath, () => {
        const canon = JSON.stringify(this._getSchemaFromStore() ?? {}, null, 2);
        if (taSchema.value.trim() === canon.trim()) return;
        taSchema.value = canon;
      }));
    }
  
    return root;
  }
  
  // ---------- schema/validator ----------
  _compileValidator() {
    this.validator = makeValidator(this.schema);
  }

  _validate(value) {
    try {
      return this.validator(value);
    } catch (e) {
      return { ok: false, errors: [{ message: String(e?.message || e) }] };
    }
  }

  // ---------- store helpers ----------
  _getValueFromStore() {
    return this.store.getPath(this.valuePath);
  }
  _setValueToStore(value) {
    this.store.setPath(this.valuePath, value);
  }

  _getSchemaFromStore() {
    return this.schemaPath ? this.store.getPath(this.schemaPath) : this.schema;
  }
  _setSchemaToStore(schemaObj) {
    if (!this.schemaPath) {
      this.schema = schemaObj;
      return;
    }
    this.store.setPath(this.schemaPath, schemaObj);
  }

  // ---------- tabs ----------
  _buildUserTab({ debounceMs }) {
    const root = new VDiv({ gap: 12 });

    const card = new Card({ title: "Visual (json-editor)" }).appendTo(root);

    // Info line
    this.userStatus = new Text("…", { muted: true }).appendTo(root);

    // mount point for json-editor
    this.userMount = ui.div().el;
    this.userMount.classList.add("json-editor");
    this.userMount.style.minHeight = "80px";
    card.el.appendChild(this.userMount);

    // Create json-editor instance
    this.userEditor = new JsonEditorAdapter({
      mount: this.userMount,
      getSchema: () => this.schema,
      getValue: () => this._getValueFromStore(),
      onChange: (val) => {
        if (!this.allowUserWriteback) return;
        this._debouncedUserWriteback(val, debounceMs);
      }
    });

    // initial render
    this.userEditor.setSchema(this.schema);
    this.userEditor.setValue(this._getValueFromStore());

    // cleanup
    root.own(() => this.userEditor?.destroy());
    return root;
  }

  _buildExpertTab() {
    const root = new VDiv({ gap: 12 });

    const top = new HDiv({ gap: 8, wrap: true, align: "center" }).appendTo(root);
    this.expertStatus = new Text("…", { muted: true }).appendTo(top);
    top.add(new Text("", { muted: true })); // spacer-ish for your layout (optional)

    const actions = new HDiv({ gap: 8, wrap: true }).appendTo(root);
    this.btnApplyValue = new Button("Apply value").appendTo(actions);
    this.btnFormatValue = new Button("Format value", { variant: "secondary" }).appendTo(actions);

    if (this.schemaPath) {
      this.btnApplySchema = new Button("Apply schema").appendTo(actions);
      this.btnFormatSchema = new Button("Format schema", { variant: "secondary" }).appendTo(actions);
    }

    const split = new HDiv({ gap: 12, wrap: true, align: "stretch" }).appendTo(root);

    const valueCard = new Card({ title: "Value JSON (Ace)" }).appendTo(split).setStyle({ flex: "1 1 520px", minWidth: "320px" });
    const schemaCard = new Card({ title: this.schemaPath ? "Schema JSON (Ace, editable)" : "Schema JSON (read-only)" })
      .appendTo(split)
      .setStyle({ flex: "1 1 520px", minWidth: "320px" });

    // Ace mounts
    const valueMount = document.createElement("div");
    valueMount.className = "ui-textarea expert";
    valueCard.el.appendChild(valueMount);

    const schemaMount = document.createElement("div");
    schemaMount.className = "ui-textarea expert";
    schemaCard.el.appendChild(schemaMount);

    this.aceValue = new AceJsonAdapter({ mount: valueMount, readOnly: false });
    this.aceSchema = new AceJsonAdapter({ mount: schemaMount, readOnly: !this.schemaPath });

    // wire buttons
    this.btnFormatValue.onClick(() => this.aceValue.format());
    this.btnApplyValue.onClick(() => this._applyExpertValue());

    if (this.schemaPath) {
      this.btnFormatSchema.onClick(() => this.aceSchema.format());
      this.btnApplySchema.onClick(() => this._applyExpertSchema());
    }

    // Live validation feedback while typing (no store write!)
    const onDraftChanged = () => this._refreshExpertStatus();
    this.aceValue.onChange(onDraftChanged);
    this.aceSchema.onChange(onDraftChanged);

    // initial load
    this.aceValue.setObject(this._getValueFromStore());
    this.aceSchema.setObject(this._getSchemaFromStore() ?? {});

    this._refreshExpertStatus();

    // cleanup
    root.own(() => {
      this.aceValue?.destroy();
      this.aceSchema?.destroy();
    });

    return root;
  }

  // ---------- sync: store -> editors ----------
  _onStoreValueChanged() {
    if (this._guardFromUser) return;

    const value = this._getValueFromStore();

    // Update user UI
    if (this.userEditor) {
      this._guardFromStore++;
      try {
        this.userEditor.setValue(value);
      } finally {
        this._guardFromStore--;
      }
    }

    // Update expert value Ace only if not same draft (avoid cursor jumps)
    if (this.aceValue && !this.aceValue.isTextDirtyComparedToObject(value)) {
      this.aceValue.setObject(value);
    }

    this._refreshUserStatus();
    this._refreshExpertStatus();
  }

  _onStoreSchemaChanged() {
    const schema = this._getSchemaFromStore();
    if (!schema) return;

    this.schema = schema;
    this._compileValidator();

    // Update user UI schema
    if (this.userEditor) {
      this._guardFromStore++;
      try {
        this.userEditor.setSchema(schema);
      } finally {
        this._guardFromStore--;
      }
    }

    // Update expert schema Ace
    if (this.aceSchema && !this.aceSchema.isTextDirtyComparedToObject(schema)) {
      this.aceSchema.setObject(schema);
    }

    this._refreshUserStatus();
    this._refreshExpertStatus();
  }

  // ---------- sync: user(json-editor) -> store (debounced, valid-only) ----------
  _debouncedUserWriteback(valueObj, debounceMs) {
    if (this._guardFromStore) return;

    clearTimeout(this._userDebounce);
    this._userDebounce = setTimeout(() => {
      this._guardFromUser++;
      try {
        const res = this._validate(valueObj);
        this._setUserStatusFromRes(res);
        if (res.ok) this._setValueToStore(valueObj);
      } finally {
        this._guardFromUser--;
      }
    }, debounceMs);
  }

  // ---------- expert apply ----------
  _applyExpertValue() {
    const { ok: parseOk, obj, error } = this.aceValue.getObjectSafe();
    if (!parseOk) {
      this._setExpertStatus(`Value parse error: ${error}`, true);
      return;
    }

    const res = this._validate(obj);
    if (!res.ok) {
      this._setExpertStatus(`Value schema invalid (${res.errors.length} errors)`, true);
      return;
    }

    this._setValueToStore(obj);
    this._setExpertStatus("✓ value applied", false);
  }

  _applyExpertSchema() {
    if (!this.schemaPath) return;

    const { ok: parseOk, obj, error } = this.aceSchema.getObjectSafe();
    if (!parseOk) {
      this._setExpertStatus(`Schema parse error: ${error}`, true);
      return;
    }

    // Try compile validator with new schema
    try {
      this.schema = obj;
      this._compileValidator();
    } catch (e) {
      this._setExpertStatus(`Schema compile error: ${String(e?.message || e)}`, true);
      return;
    }

    // Validate current value against new schema (optional but recommended)
    const val = this._getValueFromStore();
    const res = this._validate(val);
    if (!res.ok) {
      // Keep schema draft in store? You decide. Here: we still apply schema, but warn.
      this._setSchemaToStore(obj);
      this._setExpertStatus(`⚠ schema applied, but current value invalid (${res.errors.length} errors)`, true);
      return;
    }

    this._setSchemaToStore(obj);
    this._setExpertStatus("✓ schema applied", false);
  }

  // ---------- status UI ----------
  _refreshUserStatus() {
    if (!this.userStatus) return;
    const val = this._getValueFromStore();
    const res = this._validate(val);
    this._setUserStatusFromRes(res);
  }

  _setUserStatusFromRes(res) {
    if (!this.userStatus) return;
    if (res.ok) this.userStatus.setText("✓ AJV: value valid");
    else this.userStatus.setText(`AJV: invalid (${res.errors.length} errors)`);
  }

  _refreshExpertStatus() {
    if (!this.expertStatus) return;

    const valueParsed = this.aceValue?.getObjectSafe();
    const schemaParsed = this.aceSchema?.getObjectSafe();

    if (schemaParsed && !schemaParsed.ok) {
      this._setExpertStatus(`Schema parse error: ${schemaParsed.error}`, true);
      return;
    }
    if (valueParsed && !valueParsed.ok) {
      this._setExpertStatus(`Value parse error: ${valueParsed.error}`, true);
      return;
    }

    // If both parse ok, validate with current compiled validator
    if (valueParsed?.ok) {
      const res = this._validate(valueParsed.obj);
      if (res.ok) this._setExpertStatus("✓ value draft valid (not applied)", false);
      else this._setExpertStatus(`value draft invalid (${res.errors.length} errors)`, true);
    }
  }

  _setExpertStatus(text, isError) {
    if (!this.expertStatus) return;
    this.expertStatus.setText(isError ? `❌ ${text}` : text);
  }
}

// --------------------
// Adapters
// --------------------

class JsonEditorAdapter {
  constructor({ mount, getSchema, getValue, onChange }) {
    if (!window.JSONEditor) throw new Error("json-editor not loaded (window.JSONEditor)");
    this.mount = mount;
    this.onChange = onChange;

    // Create editor
    this.editor = new window.JSONEditor(mount, {
      schema: getSchema(),
      startval: getValue(),
      disable_collapse: false,
      disable_properties: false,
      disable_edit_json: true,   // we already have Ace for raw
      disable_array_reorder: false,
      no_additional_properties: false,
      required_by_default: false,
      show_errors: "interaction",
    });

    // json-editor fires "change"
    this._handler = () => {
      try {
        const val = this.editor.getValue();
        onChange?.(val);
      } catch {
        // ignore (json-editor can throw mid-change in some cases)
      }
    };
    this.editor.on("change", this._handler);
  }

  setSchema(schema) {
    // Recreate editor on schema change (simple + reliable for oneOf/anyOf)
    const currentValue = this.safeGetValue();
    this.destroy();
    this.editor = new window.JSONEditor(this.mount, {
      schema,
      startval: currentValue,
      disable_edit_json: true,
      show_errors: "interaction",
    });
    this.editor.on("change", this._handler);
  }

  setValue(value) {
    // json-editor API: setValue
    try { this.editor.setValue(value); } catch {}
  }

  safeGetValue() {
    try { return this.editor.getValue(); } catch { return {}; }
  }

  destroy() {
    try { this.editor?.destroy(); } catch {}
    this.editor = null;
  }
}

class AceJsonAdapter {
  constructor({ mount, readOnly }) {
    if (!window.ace) throw new Error("Ace not loaded (window.ace)");

    this.editor = window.ace.edit(mount);
    this.editor.setOptions({
      readOnly: !!readOnly,
      showPrintMargin: false,
      tabSize: 2,
      useSoftTabs: true,
    });

    this.editor.session.setMode("ace/mode/json");
    this.editor.session.setUseWrapMode(true);

    // Worker is optional depending on your build
    try { this.editor.session.setUseWorker(true); } catch {}

    this._changeHandlers = new Set();
    this._onChange = () => this._changeHandlers.forEach(fn => fn());
    this.editor.session.on("change", this._onChange);
  }

  onChange(fn) {
    this._changeHandlers.add(fn);
    return () => this._changeHandlers.delete(fn);
  }

  setText(text) {
    const pos = this.editor.getCursorPosition();
    this.editor.session.setValue(text ?? "");
    try { this.editor.moveCursorToPosition(pos); } catch {}
  }

  getText() {
    return this.editor.session.getValue();
  }

  setObject(obj) {
    this.setText(JSON.stringify(obj ?? {}, null, 2));
  }

  getObjectSafe() {
    const txt = this.getText();
    try {
      return { ok: true, obj: JSON.parse(txt) };
    } catch (e) {
      return { ok: false, error: String(e?.message || e) };
    }
  }

  format() {
    const { ok, obj } = this.getObjectSafe();
    if (!ok) return;
    this.setObject(obj);
  }

  // Prevent cursor jump loops: compare current text with object JSON
  isTextDirtyComparedToObject(obj) {
    const txt = this.getText().trim();
    let canonical = "";
    try { canonical = JSON.stringify(obj ?? {}, null, 2).trim(); } catch {}
    return txt !== canonical;
  }

  destroy() {
    try { this.editor?.destroy(); } catch {}
    this.editor = null;
  }
}

function safeParse(text) {
  try { return { ok: true, obj: JSON.parse(text) }; }
  catch (e) { return { ok: false, error: String(e?.message || e) }; }
}
function formatTextareaJson(ta) {
  const p = safeParse(ta.value);
  if (!p.ok) return;
  ta.value = JSON.stringify(p.obj, null, 2);
}

