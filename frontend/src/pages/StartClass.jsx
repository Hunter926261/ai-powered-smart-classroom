/**
 * Start Class — Session management page.
 * Configure duration + window, start/stop sessions, live timer + counters.
 */
import { useState, useEffect, useRef } from "react";
import PageHeader from "../components/PageHeader";
import { useApp } from "../context/AppContext";
import { startSession, stopSession } from "../services/api";
import { Play, Square, Users, UserCheck, UserX, Eye } from "lucide-react";

function padTwo(n) { return String(n).padStart(2, "0"); }

function formatTime(totalSeconds) {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (h > 0) return `${padTwo(h)}:${padTwo(m)}:${padTwo(s)}`;
  return `${padTwo(m)}:${padTwo(s)}`;
}

export default function StartClass() {
  const {
    sessionStatus, sessionData, remainingSeconds, elapsedSeconds,
    detectedCount, presentCount, lateCount, absentCount,
    fetchStats, fetchSession,
  } = useApp();

  const [duration,    setDuration]    = useState(60);
  const [window_,     setWindow]      = useState(10);
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState("");

  // Local countdown timer
  const [remaining, setRemaining] = useState(0);
  const timerRef = useRef(null);

  const isActive = sessionStatus === "active";

  // Sync with server remaining time
  useEffect(() => {
    setRemaining(remainingSeconds);
  }, [remainingSeconds]);

  // Tick down locally
  useEffect(() => {
    if (isActive && remaining > 0) {
      timerRef.current = setInterval(() => {
        setRemaining(r => Math.max(0, r - 1));
      }, 1000);
    }
    return () => clearInterval(timerRef.current);
  }, [isActive]);

  const handleStart = async () => {
    setError("");
    setLoading(true);
    try {
      await startSession(Number(duration), Number(window_));
      setRemaining(Number(duration) * 60);
      await fetchSession();
      await fetchStats();
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to start session.");
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await stopSession();
      clearInterval(timerRef.current);
      await fetchSession();
      await fetchStats();
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to stop session.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <PageHeader title="Start Class" subtitle="Configure and launch a new class session" />

      <div className="page-body">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem", alignItems: "start" }}>

          {/* ── Left: Configuration ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>

            {/* Session Config Card */}
            <div className="card">
              <div className="card-header">
                <div className="card-title">Session Configuration</div>
              </div>
              <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                  <div className="form-group">
                    <label className="form-label">Class Duration (minutes)</label>
                    <input className="form-input" type="number" min={5} max={240}
                      value={duration} onChange={e => setDuration(e.target.value)}
                      disabled={isActive} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Attendance Window (minutes)</label>
                    <input className="form-input" type="number" min={1} max={60}
                      value={window_} onChange={e => setWindow(e.target.value)}
                      disabled={isActive} />
                    <span style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>
                      Students arriving after this are marked Late
                    </span>
                  </div>
                </div>

                {error && (
                  <div style={{
                    padding: "0.6rem 0.875rem", borderRadius: "0.5rem",
                    background: "rgba(239,68,68,0.12)", color: "#f87171",
                    border: "1px solid rgba(239,68,68,0.3)", fontSize: "0.8rem"
                  }}>
                    {error}
                  </div>
                )}

                {!isActive ? (
                  <button className="btn btn-success btn-lg" onClick={handleStart} disabled={loading}>
                    <Play size={16} fill="currentColor" />
                    {loading ? "Starting..." : "Start Session"}
                  </button>
                ) : (
                  <button className="btn btn-danger btn-lg" onClick={handleStop} disabled={loading}>
                    <Square size={16} fill="currentColor" />
                    {loading ? "Stopping..." : "Stop Session"}
                  </button>
                )}
              </div>
            </div>

            {/* Rules Info */}
            <div className="card">
              <div className="card-header"><div className="card-title">Attendance Rules</div></div>
              <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "0.625rem" }}>
                {[
                  { badge: "badge-green",  label: "Present", desc: `Recognized within first ${window_} minutes` },
                  { badge: "badge-orange", label: "Late",    desc: `Recognized after ${window_} min but before end` },
                  { badge: "badge-red",    label: "Absent",  desc: "Never recognized during session" },
                ].map(({ badge, label, desc }) => (
                  <div key={label} style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <span className={`badge ${badge}`} style={{ minWidth: "60px", justifyContent: "center" }}>{label}</span>
                    <span style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ── Right: Timer + Counters ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>

            {/* Timer Card */}
            <div className="card" style={{ textAlign: "center" }}>
              <div className="card-header" style={{ justifyContent: "center" }}>
                <div>
                  <div className="card-title">
                    {isActive
                      ? <><span className="dot dot-green" style={{ marginRight: "0.375rem" }} />Time Remaining</>
                      : "Time Remaining"}
                  </div>
                </div>
              </div>
              <div className="card-body" style={{ padding: "2rem 1.25rem" }}>
                <div className="timer-display" style={{
                  color: isActive
                    ? (remaining < 300 ? "var(--color-red)" : "var(--color-blue)")
                    : "var(--text-muted)"
                }}>
                  {formatTime(isActive ? remaining : 0)}
                </div>
                <div style={{ marginTop: "0.75rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  {isActive ? `${formatTime(elapsedSeconds)} elapsed` : "Ended"}
                </div>
              </div>
            </div>

            {/* Live Counters */}
            <div className="card">
              <div className="card-header"><div className="card-title">Live Counters</div></div>
              <div className="card-body">
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.875rem" }}>
                  {[
                    { label: "Detected",  val: detectedCount, icon: Eye,       color: "var(--color-blue)" },
                    { label: "Present",   val: presentCount,  icon: UserCheck,  color: "var(--color-green)" },
                    { label: "Late",      val: lateCount,     icon: Users,      color: "var(--color-orange)" },
                    { label: "Absent",    val: absentCount,   icon: UserX,      color: "var(--color-red)" },
                  ].map(({ label, val, icon: Icon, color }) => (
                    <div key={label} style={{
                      background: "var(--color-bg-elevated)",
                      borderRadius: "0.75rem",
                      padding: "1rem",
                      display: "flex", flexDirection: "column", gap: "0.25rem",
                      border: "1px solid var(--color-border)"
                    }}>
                      <Icon size={16} color={color} />
                      <div style={{ fontSize: "1.75rem", fontWeight: 800, color }}>{val}</div>
                      <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{label}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Session Info */}
            {isActive && sessionData && (
              <div className="card">
                <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                    <strong>Started:</strong> {new Date(sessionData.start_time + "Z").toLocaleTimeString()}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                    <strong>Duration:</strong> {sessionData.duration_minutes} min &nbsp;|&nbsp;
                    <strong>Window:</strong> {sessionData.window_minutes} min
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
