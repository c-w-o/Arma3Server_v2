/**
 * Finite State Machine (FSM)
 * --------------------------
 * hdjs-inspired but modern and explicit - thanks Dieter
 *
 * Key goals:
 * - explicit states, explicit transitions
 * - enter/exit hooks (sync or async)
 * - dispatch(event, payload) that can trigger transitions
 * - optional guards
 */

export class State {
  /**
   * @param {string} name
   * @param {{
   *  enter?: (ctx, payload) => (void|Promise<void>),
   *  exit?: (ctx) => (void|Promise<void>),
   *  on?: Record<string, (ctx, payload) => (void|Promise<void>|{to:string, payload?:any}|Promise<{to:string, payload?:any}>)>,
   *  canTransition?: (ctx, toName, payload) => boolean
   * }} def
   */
  constructor(name, def = {}) {
    this.name = name;
    this.enter = def.enter ?? null;
    this.exit = def.exit ?? null;
    this.on = def.on ?? {};
    this.canTransition = def.canTransition ?? null;
  }
}

export class StateMachine {
  /**
   * @param {object} ctx - arbitrary context object (your controller/widget/model)
   * @param {{
   *  initial?: string,
   *  onTransition?: (info:{from:string|null,to:string,event:string|null,payload:any}) => void
   * }} opts
   */
  constructor(ctx = {}, opts = {}) {
    this.ctx = ctx;
    this.states = new Map();
    this.current = null; // State
    this.initial = opts.initial ?? null;
    this.onTransition = opts.onTransition ?? null;

    this._queue = Promise.resolve(); // serialize transitions/dispatches
    this._started = false;
    this._owned = [];
  }

  own(disposer) {
    if (typeof disposer === "function") this._owned.push(disposer);
    return disposer;
  }

  destroy() {
    for (const off of this._owned.splice(0)) {
      try { off(); } catch {}
    }
  }

  addState(state) {
    this.states.set(state.name, state);
    return this;
  }

  getState(name) {
    return this.states.get(name) ?? null;
  }

  is(name) {
    return !!this.current && this.current.name === name;
  }

  async start(initialName = null, payload = undefined) {
    const init = initialName ?? this.initial;
    if (!init) throw new Error("StateMachine.start: no initial state set");
    if (this._started) return;
    this._started = true;
    await this.transitionTo(init, payload, null);
  }

  /**
   * Dispatch an event to the current state.
   * The handler may:
   * - do side effects and return nothing
   * - return {to:'NextState', payload?:any} to transition
   */
  dispatch(event, payload = undefined) {
    // serialize to avoid re-entrancy bugs
    this._queue = this._queue.then(async () => {
      if (!this.current) throw new Error("StateMachine.dispatch: not started");
      const handler = this.current.on?.[event] ?? null;
      if (!handler) return;

      const res = await handler(this.ctx, payload);
      if (res && typeof res === "object" && res.to) {
        await this.transitionTo(res.to, ("payload" in res) ? res.payload : payload, event);
      }
    });
    return this._queue;
  }

  /**
   * Transition to a named state.
   */
  transitionTo(toName, payload = undefined, event = null) {
    this._queue = this._queue.then(async () => {
      const to = this.getState(toName);
      if (!to) throw new Error(`StateMachine.transitionTo: unknown state '${toName}'`);

      const from = this.current;
      // guard: check on current state
      if (from?.canTransition && !from.canTransition(this.ctx, toName, payload)) {
        return;
      }

      // exit current
      if (from?.exit) await from.exit(this.ctx);

      this.current = to;
      try {
        this.onTransition?.({
          from: from ? from.name : null,
          to: to.name,
          event,
          payload
        });
      } catch {}

      // enter next
      if (to.enter) await to.enter(this.ctx, payload);
    });
    return this._queue;
  }

  /**
   * Convenience integration: watch a Store path and dispatch an FSM event.
   *
   * @param {Store} store   - store with subscribePath(path, fn)
   * @param {string} path   - e.g. "conn.status" or "*"
   * @param {string} event  - event to dispatch
   * @param {(value:any, state:any, changedPath:string)=>any} mapPayload - optional mapping
   * @param {{immediate?:boolean}} opts
   */
  watchStore(store, path, event, mapPayload = null, opts = {}) {
    if (!store?.subscribePath) throw new Error("StateMachine.watchStore: store.subscribePath missing");
    const off = store.subscribePath(path, (value, state, changedPath) => {
      const payload = mapPayload ? mapPayload(value, state, changedPath) : value;
      this.dispatch(event, payload);
    });
    this.own(off);
    if (opts.immediate) {
      const v = store.getPath ? store.getPath(path) : undefined;
      const payload = mapPayload ? mapPayload(v, store.get?.(), path) : v;
      this.dispatch(event, payload);
    }
    return off;
  }
}