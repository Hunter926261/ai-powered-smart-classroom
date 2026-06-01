/**
 * AppContext — Global state shared across all pages.
 * Provides: session state, IoT state, WS connection status, server status.
 *
 * Polling reduced:
 *   - dashboard stats: 10s interval (was 3s)
 *   - session status: removed — now driven by WS session_update events
 *
 * New WS events handled:
 *   - session_update → updates sessionStatus, sessionData
 *   - attention_update → updates avgAttention
 *   - attendance_update → updates present/late/absent counts in real-time
 */
import { createContext, useContext, useState, useEffect, useCallback } from "react";
import socketService from "../services/socket";
import { getDashboardStats, getSessionStatus } from "../services/api";

const AppContext = createContext(null);

export function AppProvider({ children }) {
  // Connection status
  const [wsConnected,     setWsConnected]     = useState(false);
  const [serverOnline,    setServerOnline]     = useState(false);
  const [cameraOnline,    setCameraOnline]     = useState(false);

  // Session state
  const [sessionStatus,   setSessionStatus]   = useState("idle");
  const [sessionData,     setSessionData]     = useState(null);
  const [remainingSeconds,setRemainingSeconds] = useState(0);
  const [elapsedSeconds,  setElapsedSeconds]  = useState(0);

  // Live counters
  const [occupancy,       setOccupancy]       = useState(0);
  const [presentCount,    setPresentCount]     = useState(0);
  const [lateCount,       setLateCount]       = useState(0);
  const [absentCount,     setAbsentCount]     = useState(0);
  const [detectedCount,   setDetectedCount]   = useState(0);

  // Attention average (live from attention_update WS event)
  const [avgAttention,    setAvgAttention]    = useState(0);

  // IoT state
  const [iotStatus,       setIotStatus]       = useState({ light_on: false, fan_on: false, mode: "AUTO" });

  // Dashboard stats
  const [dashStats,       setDashStats]       = useState({
    total_students: 0,
    present_today:  0,
    phone_alerts_count: 0,
    recent_activity: []
  });

  // Phone alerts
  const [phoneAlerts,     setPhoneAlerts]     = useState([]);

  // ---- Polling: dashboard stats every 10s (reduced from 3s) ----
  const fetchStats = useCallback(async () => {
    try {
      const { data } = await getDashboardStats();
      setServerOnline(true);
      setCameraOnline(data.active_cameras > 0);
      setDashStats(data);
      setSessionStatus(data.session_status || "idle");
      setPresentCount(data.present_count  || 0);
      setLateCount(data.late_count        || 0);
      setAbsentCount(data.absent_count    || 0);
      setOccupancy(data.occupancy         || 0);
      if (data.iot_status) setIotStatus(data.iot_status);
    } catch {
      setServerOnline(false);
    }
  }, []);

  // One-time session status fetch on mount (to restore state after refresh)
  const fetchSession = useCallback(async () => {
    try {
      const { data } = await getSessionStatus();
      setSessionStatus(data.status);
      setSessionData(data.session);
      setRemainingSeconds(data.remaining_seconds || 0);
      setElapsedSeconds(data.elapsed_seconds     || 0);
      setDetectedCount(data.detected_count       || 0);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    // Initial fetches
    fetchStats();
    fetchSession();

    // Dashboard stats polled every 10s (session state now driven by WS)
    const statsInterval = setInterval(fetchStats, 10000);

    return () => {
      clearInterval(statsInterval);
    };
  }, [fetchStats, fetchSession]);

  // ---- WebSocket connection ----
  useEffect(() => {
    socketService.connect();
    const unsubStatus = socketService.onStatusChange(setWsConnected);

    // Occupancy events (real-time person count)
    const unsubOcc = socketService.on("occupancy", ({ count }) => {
      setOccupancy(count);
      setDetectedCount(count);
    });

    // Phone alert events
    const unsubPhone = socketService.on("phone_alert", (alert) => {
      setPhoneAlerts((prev) => [alert, ...prev].slice(0, 20));
    });

    // Session update events — replaces 2s polling
    const unsubSession = socketService.on("session_update", ({ status, session }) => {
      setSessionStatus(status || "idle");
      setSessionData(session || null);
      // Refresh stats once on session state change
      fetchStats();
    });

    // Attendance update events — real-time count without polling
    const unsubAttendance = socketService.on("attendance_update", (data) => {
      setPresentCount(data.present  || 0);
      setLateCount(data.late        || 0);
      setAbsentCount(data.absent    || 0);
      setRemainingSeconds(data.remaining_seconds || 0);
    });

    // Attention update events — live avg attention score
    const unsubAttention = socketService.on("attention_update", (data) => {
      setAvgAttention(data.avg_score || 0);
    });

    return () => {
      unsubStatus();
      unsubOcc();
      unsubPhone();
      unsubSession();
      unsubAttendance();
      unsubAttention();
    };
  }, [fetchStats]);

  const value = {
    // Connection
    wsConnected, serverOnline, cameraOnline,
    // Session
    sessionStatus, sessionData, remainingSeconds, elapsedSeconds,
    setSessionStatus, setSessionData,
    // Counts
    occupancy, presentCount, lateCount, absentCount, detectedCount,
    // Attention
    avgAttention,
    // IoT
    iotStatus, setIotStatus,
    // Dashboard
    dashStats,
    // Alerts
    phoneAlerts,
    // Refresh helpers
    fetchStats, fetchSession,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used inside AppProvider");
  return ctx;
}

export default AppContext;
