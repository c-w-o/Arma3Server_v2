/**
 * Timer
 * -----
 * Small helper similar to hdjs' Timer, thanks Dieter:
 * - tracks timeout id so stop() reliably cancels
 * - idempotent stop()
 * - can be used as repeating timer (auto-reschedule)
 */
export class Timer {
  constructor(fn, intervalMs = 0, { repeat = true } = {}) {
    this.fn = fn;
    this.intervalMs = intervalMs;
    this.repeat = repeat;

    this.nrCalled = 0;
    this.runAllowed = false;
    this._running = false;
    this._timeoutId = null;

    this._handler = this._handler.bind(this);
  }

  _handler() {
    this._running = false;
    this._timeoutId = null;
    if (!this.runAllowed) return;

    this.nrCalled++;
    try { this.fn?.(); } catch {}

    if (this.repeat && this.runAllowed) {
      this.start();
    }
  }

  start() {
    if (this._running) return;
    this.runAllowed = true;
    this._running = true;
    this._timeoutId = setTimeout(this._handler, this.intervalMs);
  }

  stop() {
    this.runAllowed = false;
    this._running = false;
    if (this._timeoutId !== null) {
      try { clearTimeout(this._timeoutId); } catch {}
      this._timeoutId = null;
    }
  }

  reset() {
    this.nrCalled = 0;
  }
}