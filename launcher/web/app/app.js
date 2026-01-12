import {
  ui,
  dom,
  Store,
  Timer,
  Button,
  Text,
  Heading,
  Pre,
  Card,
  HDiv,
  VDiv,
  HSpacer,
  Tabs,
  TableView,
} from "/ui-kit-0/src/ui-kit-0.js";

async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const isJson = (res.headers.get("content-type") || "").includes("application/json");
  const data = isJson ? await res.json() : await res.text();
  if (!res.ok) {
    const detail = isJson ? (data?.detail || JSON.stringify(data)) : String(data);
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  return data;
}

function fmtStatusMap(status) {
  const rows = [];
  for (const [name, st] of Object.entries(status || {})) {
    rows.push({
      name,
      running: !!st?.running,
      pid: st?.pid ?? "-",
      started_at: st?.started_at ?? "-",
    });
  }
  rows.sort((a, b) => a.name.localeCompare(b.name));
  return rows;
}

// --- Store ---
const store = new Store({
  conn: { ok: false, error: null },
  status: {},
  plan: null,
  logs: { list: [], active: null, cursor: null, entries: [] },
});

async function refreshStatus() {
  try {
    const r = await api("/status");
    store.batch(() => {
      store.setPath("conn.ok", true);
      store.setPath("conn.error", null);
      store.setPath("status", r?.data || {});
    });
  } catch (e) {
    store.batch(() => {
      store.setPath("conn.ok", false);
      store.setPath("conn.error", String(e?.message || e));
    });
  }
}

async function refreshPlan() {
  const p = await api("/plan");
  store.setPath("plan", p);
}

async function refreshLogList() {
  const r = await api("/logs");
  store.setPath("logs.list", r?.logs || []);
}

async function loadLog(logId, { mode = "tail" } = {}) {
  const base = `/logs/${encodeURIComponent(logId)}`;
  const cursor = store.getPath("logs.cursor");
  const q = mode === "cursor" && cursor ? `?cursor=${encodeURIComponent(cursor)}&max_lines=400` : `?tail=400`;
  const r = await api(base + q);
  store.batch(() => {
    store.setPath("logs.active", logId);
    store.setPath("logs.cursor", r?.cursor || null);
    store.setPath("logs.entries", r?.entries || []);
  });
}

async function action(path, { dryRun = false } = {}) {
  const q = path === "/sync" ? (dryRun ? "?dry_run=true" : "?dry_run=false") : "";
  return api(path + q, { method: "POST" });
}

// --- UI ---
const root = dom.get("#app");

const header = new HDiv({ gap: 12, align: "center", wrap: true }).add(
  new Heading("Arma Launcher", { level: 2 }),
  new HSpacer(),
);

const badge = ui.span().cls("ui-badge").text("offline");
header.add(badge);

store.subscribePath("conn", (conn) => {
  const ok = !!conn?.ok;
  badge.text(ok ? "online" : "offline");
  badge.cls("ui-badge", ok ? "ok" : "error");
  if (!ok && conn?.error) badge.attr("title", conn.error);
});

// --- Status tab ---
const statusTable = new TableView({
  columns: [
    { key: "name", label: "Process" },
    { key: "running", label: "Running", format: (v) => (v ? "yes" : "no") },
    { key: "pid", label: "PID", align: "right" },
    { key: "started_at", label: "Started" },
  ],
  data: [],
});

store.subscribePath("status", (st) => {
  statusTable.setData(fmtStatusMap(st));
});

const btnStart = new Button("Start", { variant: "primary" }).onClick(async () => {
  await action("/start");
  await refreshStatus();
});
const btnStop = new Button("Stop", { variant: "danger" }).onClick(async () => {
  await action("/stop");
  await refreshStatus();
});
const btnRestart = new Button("Restart", { variant: "secondary" }).onClick(async () => {
  await action("/restart");
  await refreshStatus();
});
const btnSyncDry = new Button("Sync (dry-run)", { variant: "secondary" }).onClick(async () => {
  const r = await action("/sync", { dryRun: true });
  store.setPath("plan", r?.data || null);
});
const btnSync = new Button("Sync", { variant: "primary" }).onClick(async () => {
  await action("/sync", { dryRun: false });
  await refreshStatus();
});

const statusCard = new Card({ title: "Processes" }).add(statusTable);
const controlsCard = new Card({ title: "Actions" }).add(
  new HDiv({ gap: 10, wrap: true }).add(btnStart, btnStop, btnRestart, btnSyncDry, btnSync)
);

const statusTab = new VDiv({ gap: 12 }).add(controlsCard, statusCard);

// --- Plan tab ---
const planPre = new Pre("(not loaded)");
store.subscribePath("plan", (p) => {
  planPre.text(p ? JSON.stringify(p, null, 2) : "(not loaded)");
});

const planTab = new VDiv({ gap: 12 }).add(
  new Card({ title: "Plan (dry-run)" }).add(
    new HDiv({ gap: 10, align: "center", wrap: true }).add(
      new Text("This is always safe; it does not touch SteamCMD or the filesystem.", { muted: true }),
      new HSpacer(),
      new Button("Refresh", { variant: "secondary" }).onClick(refreshPlan),
    ),
    planPre
  )
);

// --- Logs tab ---
const logSelect = ui.select().cls("ui-select");
const logPre = new Pre("Select a log.");

function renderLogOptions(list, active) {
  logSelect.clear();
  logSelect.add(ui.option("Select log…", ""));
  for (const id of list) {
    const opt = ui.option(id, id);
    if (id === active) opt.attr("selected", "selected");
    logSelect.add(opt);
  }
}

store.subscribePath("logs.list", (list) => renderLogOptions(list || [], store.getPath("logs.active")));
store.subscribePath("logs.active", (active) => renderLogOptions(store.getPath("logs.list") || [], active));
store.subscribePath("logs.entries", (entries) => {
  const lines = (entries || []).map((e) => e.line);
  logPre.text(lines.join("\n") || "(empty)");
});

logSelect.on("change", async () => {
  const v = logSelect.el.value;
  if (!v) return;
  store.setPath("logs.cursor", null);
  await loadLog(v, { mode: "tail" });
});

const btnReload = new Button("Reload", { variant: "secondary" }).onClick(async () => {
  const id = store.getPath("logs.active");
  if (!id) return;
  store.setPath("logs.cursor", null);
  await loadLog(id, { mode: "tail" });
});

const btnFollow = new Button("Follow", { variant: "secondary" }).onClick(async () => {
  const id = store.getPath("logs.active");
  if (!id) return;
  await loadLog(id, { mode: "cursor" });
});

const logsTab = new VDiv({ gap: 12 }).add(
  new Card({ title: "Logs" }).add(
    new HDiv({ gap: 10, align: "center", wrap: true }).add(
      ui.div().add(new Text("Log file", { muted: true }), logSelect),
      new HSpacer(),
      btnReload,
      btnFollow,
      new Button("Refresh list", { variant: "secondary" }).onClick(refreshLogList),
    ),
    logPre
  )
);

// --- Tabs shell ---
const tabs = new Tabs({ active: "status" })
  .addTab("status", "Status", statusTab)
  .addTab("plan", "Plan", planTab)
  .addTab("logs", "Logs", logsTab);

ui.mount(root, new VDiv({ gap: 12 }).add(header, tabs));

// --- Boot ---
await refreshStatus();
await refreshLogList();

const statusTimer = new Timer(refreshStatus, 2000, { repeat: true });
statusTimer.start();