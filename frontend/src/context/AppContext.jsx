/**
 * AppContext — Global state shared across all pages.
 * Provides: session state, IoT state, WS connection status, server status.
 */
import { createContext, useContext, useState, useEffect, useCallback } from "react";
import socketService from "../services/socket";
import { getDashboardStats, getSessionStatus, getIoTStatus } from "../services/api";

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

  // ---- Polling: dashboard stats every 3 seconds ----
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

    const statsInterval   = setInterval(fetchStats,   3000);
    const sessionInterval = setInterval(fetchSession, 2000);

    return () => {
      clearInterval(statsInterval);
      clearInterval(sessionInterval);
    };
  }, [fetchStats, fetchSession]);

  // ---- WebSocket connection ----
  useEffect(() => {
    socketService.connect();
    const unsubStatus = socketService.onStatusChange(setWsConnected);

    // Occupancy events
    const unsubOcc = socketService.on("occupancy", ({ count }) => {
      setOccupancy(count);
      setDetectedCount(count);
    });

    // Phone alert events
    const unsubPhone = socketService.on("phone_alert", (alert) => {
      setPhoneAlerts((prev) => [alert, ...prev].slice(0, 20));
    });

    return () => {
      unsubStatus();
      unsubOcc();
      unsubPhone();
    };
  }, []);

  const value = {
    // Connection
    wsConnected, serverOnline, cameraOnline,
    // Session
    sessionStatus, sessionData, remainingSeconds, elapsedSeconds,
    setSessionStatus, setSessionData,
    // Counts
    occupancy, presentCount, lateCount, absentCount, detectedCount,
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
