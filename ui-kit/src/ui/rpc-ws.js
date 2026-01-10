/**
 * JsonRpcWebSocketClient
 * ----------------------
 * hdjs-inspired JSON-RPC over WebSocket, thanks Dieter:
 * - Promise-based call()
 * - notify() (no id)
 * - per-call timeout
 * - optional queue while disconnected
 * - pending calls rejected on disconnect
 */
export class JsonRpcWebSocketClient {
  constructor(url, {
    autoReconnectMs = 0,
    callTimeoutMs = 0,
    queueWhenDisconnected = false,
    onMessageDefault = null,
    onOpen = null,
    onClose = null,
  } = {}) {
    this.url = url;
    this.autoReconnectMs = autoReconnectMs;
    this.callTimeoutMs = callTimeoutMs;
    this.queueWhenDisconnected = queueWhenDisconnected;
    this.onMessageDefault = onMessageDefault;
    this.onOpen = onOpen;
    this.onClose = onClose;

    this.ws = null;
    this.connected = false;

    this._id = 1;
    this._pending = new Map(); // id -> { resolve, reject, timeoutId }
    this._sendQueue = [];

    this._reconnectTimer = null;

    this._onWsOpen = this._onWsOpen.bind(this);
    this._onWsClose = this._onWsClose.bind(this);
    this._onWsMessage = this._onWsMessage.bind(this);
    this._onWsError = this._onWsError.bind(this);
  }

  isConnected() { return !!this.connected && !!this.ws && this.ws.readyState === WebSocket.OPEN; }

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) return;
    try {
      this.ws = new WebSocket(this.url);
      this.ws.addEventListener("open", this._onWsOpen);
      this.ws.addEventListener("close", this._onWsClose);
      this.ws.addEventListener("message", this._onWsMessage);
      this.ws.addEventListener("error", this._onWsError);
    } catch (e) {
      this._scheduleReconnect();
    }
  }

  disconnect() {
    this._clearReconnect();
    try { this.ws?.close(); } catch {}
  }

  destroy() {
    this.disconnect();
    this._failAllPending({ code: -32000, message: "destroyed" });
    this._sendQueue.length = 0;
    this.ws = null;
  }

  _clearReconnect() {
    if (this._reconnectTimer) {
      try { clearTimeout(this._reconnectTimer); } catch {}
      this._reconnectTimer = null;
    }
  }

  _scheduleReconnect() {
    this._clearReconnect();
    if (!this.autoReconnectMs || this.autoReconnectMs <= 0) return;
    this._reconnectTimer = setTimeout(() => this.connect(), this.autoReconnectMs);
  }

  _failAllPending(err) {
    for (const [id, p] of this._pending.entries()) {
      if (p.timeoutId) { try { clearTimeout(p.timeoutId); } catch {} }
      try { p.reject(err); } catch {}
      this._pending.delete(id);
    }
  }

  _onWsOpen() {
    this.connected = true;
    try { this.onOpen?.(); } catch {}

    // Flush queue
    if (this.queueWhenDisconnected && this._sendQueue.length) {
      const q = this._sendQueue.splice(0);
      for (const msg of q) this._sendRaw(msg);
    }
  }

  _onWsClose() {
    this.connected = false;
    // reject pending calls to avoid hanging promises
    this._failAllPending({ code: -32000, message: "disconnected" });
    try { this.onClose?.(); } catch {}
    this._scheduleReconnect();
  }

  _onWsError() {
    // Treat errors as reconnect triggers
    this._scheduleReconnect();
  }

  _onWsMessage(ev) {
    let msg = null;
    try { msg = JSON.parse(ev.data); } catch {
      try { this.onMessageDefault?.(ev.data); } catch {}
      return;
    }

    // Response: {id, result|error}
    if (msg && Object.prototype.hasOwnProperty.call(msg, "id") && (Object.prototype.hasOwnProperty.call(msg, "result") || Object.prototype.hasOwnProperty.call(msg, "error"))) {
      const id = msg.id;
      const p = this._pending.get(id);
      if (!p) return;
      if (p.timeoutId) { try { clearTimeout(p.timeoutId); } catch {} }
      this._pending.delete(id);
      if (Object.prototype.hasOwnProperty.call(msg, "error") && msg.error) {
        p.reject(msg.error);
      } else {
        p.resolve(msg.result);
      }
      return;
    }

    // Notification or server-sent request (no result/error)
    try { this.onMessageDefault?.(msg); } catch {}
  }

  _sendRaw(msg) {
    if (!this.isConnected()) return false;
    try { this.ws.send(msg); return true; } catch { return false; }
  }

  _send(msgObj) {
    const msg = JSON.stringify(msgObj);
    if (this.isConnected()) return this._sendRaw(msg);

    if (this.queueWhenDisconnected) {
      this._sendQueue.push(msg);
      this.connect(); // ensure connection attempt
      return true;
    }
    return false;
  }

  notify(method, params = []) {
    return this._send({ jsonrpc: "2.0", method, params });
  }

  call(method, params = [], { timeoutMs = null } = {}) {
    const id = this._id++;
    const t = (timeoutMs ?? this.callTimeoutMs) || 0;

    return new Promise((resolve, reject) => {
      let timeoutId = null;
      if (t > 0) {
        timeoutId = setTimeout(() => {
          if (this._pending.has(id)) {
            this._pending.delete(id);
            reject({ code: -32001, message: "timeout", data: { timeoutMs: t } });
          }
        }, t);
      }

      this._pending.set(id, { resolve, reject, timeoutId });
      const ok = this._send({ jsonrpc: "2.0", id, method, params });
      if (!ok) {
        if (timeoutId) { try { clearTimeout(timeoutId); } catch {} }
        this._pending.delete(id);
        reject({ code: -32000, message: "send failed (not connected)" });
      }
    });
  }
}