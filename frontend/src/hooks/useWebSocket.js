/**
 * useWebSocket — React hook for WebSocket event subscriptions.
 * Connects to the singleton socket service and subscribes to events.
 */
import { useEffect, useRef } from "react";
import socketService from "../services/socket";

/**
 * @param {string|string[]} eventTypes - Event type(s) to subscribe to
 * @param {function} callback - Called with event data when event fires
 * @param {any[]} deps - Optional dependency array
 */
export function useWebSocket(eventTypes, callback, deps = []) {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    // Ensure connection is active
    socketService.connect();

    const types = Array.isArray(eventTypes) ? eventTypes : [eventTypes];
    const unsubscribers = types.map((type) =>
      socketService.on(type, (data) => callbackRef.current(data, type))
    );

    return () => {
      unsubscribers.forEach((unsub) => unsub());
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

/**
 * useWsStatus — tracks WebSocket connection status.
 * @returns {boolean} isConnected
 */
export function useWsStatus() {
  const [connected, setConnected] = window.React
    ? window.React.useState(false)
    : [false, () => {}];

  // We'll do this properly via AppContext instead
  return connected;
}

export default useWebSocket;
