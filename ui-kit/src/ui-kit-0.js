
export const UI_KIT_NAME = "ui-kit";
export const UI_KIT_MAJOR = 0;
export const UI_KIT_MINOR = 7;
export const UI_KIT_PATCH = 0;

export const UI_KIT_VERSION = `${UI_KIT_MAJOR}.${UI_KIT_MINOR}.${UI_KIT_PATCH}`;
/**
 * ui-kit-0
 * ========
 *
 * A minimalist UI kit designed for:
 * - Native ES Modules in the browser
 * - Offline-capable, explicitly managed third-party libraries
 * - Zero runtime build tooling
 *
 * ------------------------------------------------------------
 * DEPENDENCIES
 * ------------------------------------------------------------
 *
 * 1) No external dependencies (Core)
 * ----------------------------------
 * The following modules work fully standalone and do NOT rely
 * on any third-party libraries:
 *
 * - base.js
 * - layout.js
 * - controls.js
 * - tabs.js
 * - table.js
 * - selection.js
 * - store.js
 *
 *
 * 2) Optional third-party dependencies
 * ------------------------------------
 * The features below expect global browser objects that MUST
 * be loaded via <script> tags BEFORE ui-kit-0.js.
 *
 * a) JSON Schema validation (Draft-07)
 * -----------------------------------
 * Required for:
 * - validation.js
 * - schema-config-editor.js
 *
 * Expected global:
 * - window.ajv7   (AJV Draft-07 bundle)
 *
 * Recommended source (offline-capable):
 *   https://cdnjs.cloudflare.com/ajax/libs/ajv/8.x/ajv7.bundle.min.js
 *
 *
 * b) JSON Editor (end-user form UI, oneOf / anyOf support)
 * -------------------------------------------------------
 * Required for:
 * - schema-config-editor.js (User / Visual view)
 *
 * Expected global:
 * - window.JSONEditor
 *
 * Recommended source:
 *   https://unpkg.com/@json-editor/json-editor@2.x/dist/jsoneditor.js
 *
 *
 * c) Ace Editor (expert / raw JSON editing)
 * -----------------------------------------
 * Required for:
 * - schema-config-editor.js (Expert view)
 *
 * Expected global:
 * - window.ace
 *
 * Required Ace files (noconflict build):
 * - ace.js
 * - mode-json.js
 * - worker-json.js
 *
 * Recommended source:
 *   https://github.com/ajaxorg/ace-builds
 *
 *
 * d) Chart.js
 * -----------
 * Required for:
 * - chart.js
 *
 * Expected global:
 * - window.Chart
 *
 * Recommended source:
 *   Chart.js UMD build (locally vendored)
 *
 *
 * ------------------------------------------------------------
 * SCRIPT LOAD ORDER (Browser)
 * ------------------------------------------------------------
 *
 * <script src="ajv7.bundle.min.js"></script>
 * <script src="ace.js"></script>
 * <script src="mode-json.js"></script>
 * <script src="worker-json.js"></script>
 * <script src="jsoneditor.js"></script>
 * <script src="chart.umd.min.js"></script>
 * <script type="module" src="ui-kit-0.js"></script>
 *
 *
 * ------------------------------------------------------------
 * DESIGN PRINCIPLES
 * ------------------------------------------------------------
 *
 * - No runtime bundler
 * - No implicit imports
 * - All third-party libraries are explicit and global
 * - AJV is the single source of truth for JSON validation
 * - UI components encapsulate behavior but never hide dependencies
 *
 *
 * ------------------------------------------------------------
 * THIRD-PARTY LICENSES
 * ------------------------------------------------------------
 *
 * - AJV: MIT
 * - json-editor: MIT
 * - Ace Editor: BSD-3-Clause
 * - Chart.js: MIT
 *
 * See src/sbom.json for exact versions and checksums.
 */
 
 import { FALLBACK_CSS } from "./ui/fallback-css.js";

function ensureUiCss() {
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue("--ui-css-loaded")
    .trim();

  if (v === "1") return;

  const style = document.createElement("style");
  style.setAttribute("data-ui-fallback", "true");
  style.textContent = FALLBACK_CSS;
  document.head.appendChild(style);

  console.warn("[ui-kit] CSS not loaded → fallback CSS applied");
}

ensureUiCss();
 
export * from "./ui/base.js";
export * from "./ui/dom.js";
export * from "./ui/chart.js";
export * from "./ui/controls.js";
export * from "./ui/dialog-stack.js";
export * from "./ui/fsm.js";
export * from "./ui/image.js";
export * from "./ui/json-editor.js";
export * from "./ui/layout.js";
export * from "./ui/rpc-ws.js";
export * from "./ui/schema-config-editor.js";
export * from "./ui/selection.js";
export * from "./ui/store.js";
export * from "./ui/tabs.js";
export * from "./ui/table.js";
export * from "./ui/timer.js";
export * from "./ui/ui.js";
export * from "./ui/validation.js";

// src/ui-kit-0.js (am Ende)
export const UI = {
  version: UI_KIT_VERSION,
};