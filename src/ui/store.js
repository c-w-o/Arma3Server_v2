// src/ui/store.js

function clone(x) {
  if (typeof structuredClone === "function") return structuredClone(x);
  // Fallback: reicht für plain JSON-Daten (Objekte/Arrays/Numbers/Strings/Bools)
  return JSON.parse(JSON.stringify(x));
}
  
export class Store {
  constructor(initial = {}) {
    this.state = clone(initial);
    this.listeners = new Set();     // global listeners
    this.pathListeners = new Map(); // path -> Set(fn)

     this._batchDepth = 0;
    this._batchedPaths = new Set();
  }

  get() {
    return this.state;
  }
  
  // Get by "a.b.c"
  getPath(path) {
    if (!path) return this.state;
    const parts = path.split(".");
    let cur = this.state;
    for (const p of parts) {
      if (cur == null) return undefined;
      cur = cur[p];
    }
    return cur;
  }

  // Patch by "a.b.c"
  setPath(path, value) {
    const parts = path.split(".");
    if (parts.length === 0) return;

    // clone-on-write along the path (deterministic, no accidental shared refs)
    const newState = clone(this.state);

    let cur = newState;
    for (let i = 0; i < parts.length - 1; i++) {
      const k = parts[i];
      if (typeof cur[k] !== "object" || cur[k] === null) cur[k] = {};
      cur = cur[k];
    }
    cur[parts[parts.length - 1]] = value;

    this.state = newState;
    this._emit(path);
  }

  updatePath(path, fn) {
    const prev = this.getPath(path);
    this.setPath(path, fn(prev));
  }

  // Set whole state (replaces)
  set(next) {
    this.state = clone(next);
    this._emit("*");
  }

  // Shallow merge at root
  merge(partial) {
    this.state = { ...this.state, ...clone(partial) };
    this._emit("*");
  }

  batch(fn) {
    this._batchDepth++;
    try { fn(); }
    finally {
      this._batchDepth--;
      if (this._batchDepth === 0 && this._batchedPaths.size) {
        this._batchedPaths.clear();
        this._emit("*");
      }
    }
  }

  subscribe(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  subscribePath(path, fn) {
    if (!this.pathListeners.has(path)) this.pathListeners.set(path, new Set());
    this.pathListeners.get(path).add(fn);
    return () => this.pathListeners.get(path)?.delete(fn);
  }

  _emit(path) {
    if (this._batchDepth > 0) {
      this._batchedPaths.add(path);
      return;
    }
    // Global listeners: receive (state, changedPath)
    for (const fn of this.listeners) fn(this.state, path);

    // Path listeners: exact path and "*" listeners
    const exact = this.pathListeners.get(path);
    if (exact) for (const fn of exact) fn(this.getPath(path), this.state, path);

    const star = this.pathListeners.get("*");
    if (star) for (const fn of star) fn(undefined, this.state, path);
  }
}