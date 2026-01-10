// =====================================================
// UI KIT 0 — Fallback CSS
// Applied only if ui-kit CSS is missing
// =====================================================

export const FALLBACK_CSS = `
* { box-sizing: border-box; }

body {
  font-family: system-ui, sans-serif;
  font-size: 14px;
  margin: 0;
  padding: 8px;
}

.card {
  border: 1px solid #999;
  padding: 8px;
  margin-bottom: 8px;
}

.ui-btn,
button {
  padding: 6px 10px;
  border: 1px solid #888;
  background: #eee;
  cursor: pointer;
}

.ui-input,
.ui-select,
.ui-textarea,
input,
select,
textarea {
  padding: 6px;
  border: 1px solid #888;
  width: 100%;
}

table {
  border-collapse: collapse;
  width: 100%;
}

th, td {
  border: 1px solid #999;
  padding: 4px 6px;
}

.muted {
  opacity: 0.7;
}
`;