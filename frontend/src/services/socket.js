/**
 * WebSocket Service — Smart Classroom Manager
 * Singleton WebSocket connection with auto-reconnect.
 * Backend WS endpoint: ws://127.0.0.1:8000/ws
 */

const WS_URL = "ws://127.0.0.1:8000/ws";

class SocketService {
  constructor() {
    this.ws = null;
    this.listeners = {};      // { eventType: [callbacks] }
    this.reconnectDelay = 3000;
    this.reconnectTimer = null;
    this.connected = false;
    this._statusListeners = [];
  }

  /** Connect to the WebSocket server. */
  connect() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;

    try {
      this.ws = new WebSocket(WS_URL);

      this.ws.onopen = () => {
        this.connected = true;
        console.log("[WS] Connected");
        this._notifyStatus(true);
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const { type, data } = payload;
          // Dispatch to all registered listeners for this event type
          if (this.listeners[type]) {
            this.listeners[type].forEach((cb) => cb(data));
          }
          // Also dispatch to wildcard listeners
          if (this.listeners["*"]) {
            this.listeners["*"].forEach((cb) => cb(payload));
          }
        } catch (e) {
          console.warn("[WS] Parse error:", e);
        }
      };

      this.ws.onclose = () => {
        this.connected = false;
        console.log("[WS] Disconnected — reconnecting...");
        this._notifyStatus(false);
        this._scheduleReconnect();
      };

      this.ws.onerror = (err) => {
        console.warn("[WS] Error:", err);
        this.ws.close();
      };
    } catch (e) {
      console.warn("[WS] Connection failed:", e);
      this._scheduleReconnect();
    }
  }

  /** Disconnect and stop reconnecting. */
  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) this.ws.close();
    this.connected = false;
  }

  /**
   * Subscribe to a WebSocket event type.
   * @param {string} type - Event type (e.g. "recognition", "occupancy", "phone_alert")
   * @param {function} callback - Called with the event data
   * @returns {function} Unsubscribe function
   */
  on(type, callback) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(callback);
    // Return unsubscribe function
    return () => {
      this.listeners[type] = this.listeners[type].filter((cb) => cb !== callback);
    };
  }

  /** Subscribe to connection status changes. */
  onStatusChange(callback) {
    this._statusListeners.push(callback);
    // Immediately call with current status
    callback(this.connected);
    return () => {
      this._statusListeners = this._statusListeners.filter((cb) => cb !== callback);
    };
  }

  _notifyStatus(connected) {
    this._statusListeners.forEach((cb) => cb(connected));
  }

  _scheduleReconnect() {
    if (!this.reconnectTimer) {
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connect();
      }, this.reconnectDelay);
    }
  }
}

// Singleton export
const socketService = new SocketService();
export default socketService;
