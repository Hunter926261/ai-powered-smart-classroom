/**
 * Attendance — Live camera + real-time attendance tracking.
 * Shows live feed, attendance log table, session summary, CSV export, manual override.
 */
import { useState, useEffect, useCallback } from "react";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { useApp } from "../context/AppContext";
import useWebSocket from "../hooks/useWebSocket";
import {
  getLiveAttendance, overrideAttendance, exportAttendanceCSV, VIDEO_FEED_URL
} from "../services/api";
import { Download, Search, Edit3, Check, X } from "lucide-react";

export default function Attendance() {
  const { sessionStatus, cameraOnline, presentCount, lateCount, absentCount } = useApp();

  const [attendance, setAttendance] = useState([]);
  const [search,     setSearch]     = useState("");
  const [showFeed,   setShowFeed]   = useState(true);
  const [overrideTarget, setOverrideTarget] = useState(null);
  const [overrideVal,    setOverrideVal]    = useState("Present");

  const fetchAttendance = useCallback(async () => {
    try {
      const { data } = await getLiveAttendance();
      setAttendance(data.attendance || []);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    fetchAttendance(); // Initial fetch on mount
    // WS recognition event below triggers re-fetch on every recognition
    // No polling interval needed
  }, [fetchAttendance]);

  // WebSocket: real-time recognition event
  useWebSocket("recognition", () => { fetchAttendance(); });

  const filtered = attendance.filter(r =>
    r.name?.toLowerCase().includes(search.toLowerCase()) ||
    r.roll_no?.toLowerCase().includes(search.toLowerCase())
  );

  const handleOverride = async () => {
    if (!overrideTarget) return;
    try {
      await overrideAttendance(overrideTarget, overrideVal);
      setOverrideTarget(null);
      fetchAttendance();
    } catch (e) {
      console.error("Override failed", e);
    }
  };

  const isActive = sessionStatus === "active";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <PageHeader title="Attendance" subtitle="Real-time face detection and attendance tracking" />

      <div className="page-body">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 220px", gap: "1.25rem", alignItems: "start" }}>

          {/* ── Left: Camera + Table ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>

            {/* Live Camera Feed */}
            <div className="card">
              <div className="card-header">
                <div className="card-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  Live Camera Feed
                  {isActive && <span className="badge badge-green"><span className="dot dot-green" /> Active</span>}
                </div>
                <button className="btn btn-ghost btn-sm" onClick={() => setShowFeed(v => !v)}>
                  {showFeed ? "Hide Feed" : "Show Feed"}
                </button>
              </div>
              {showFeed && (
                <div className="card-body" style={{ padding: "0.75rem" }}>
                  <div className="camera-container">
                    <img src={VIDEO_FEED_URL} alt="Live feed" className="camera-feed" />
                    {isActive && (
                      <div className="camera-rec-badge">
                        <span className="dot dot-red" /> REC
                      </div>
                    )}
                    <div className="camera-info-badge">
                      {cameraOnline
                        ? <><span className="dot dot-green" style={{ marginRight: "0.3rem" }} />Camera active — face recognition running</>
                        : "Camera inactive"}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Attendance Log */}
            <div className="card">
              <div className="card-header">
                <div className="card-title">Attendance Log</div>
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <div style={{ position: "relative" }}>
                    <Search size={13} style={{ position: "absolute", left: "0.5rem", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
                    <input className="form-input" placeholder="Search..." value={search}
                      onChange={e => setSearch(e.target.value)}
                      style={{ paddingLeft: "1.75rem", width: "180px", height: "2rem", fontSize: "0.78rem" }} />
                  </div>
                  <a href={exportAttendanceCSV()} download className="btn btn-ghost btn-sm">
                    <Download size={13} /> Export CSV
                  </a>
                </div>
              </div>

              {filtered.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-state-title">No attendance records</div>
                  <div className="empty-state-sub">Start a class session to begin tracking</div>
                </div>
              ) : (
                <div className="table-container" style={{ border: "none" }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Roll No.</th>
                        <th>Entry Time</th>
                        <th>Status</th>
                        <th style={{ textAlign: "right" }}>Override</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((r, i) => (
                        <tr key={i}>
                          <td style={{ fontWeight: 500 }}>{r.name}</td>
                          <td style={{ color: "var(--text-secondary)" }}>{r.roll_no || "—"}</td>
                          <td style={{ color: "var(--text-muted)", fontSize: "0.78rem" }}>
                            {r.timestamp ? new Date(r.timestamp + "Z").toLocaleTimeString() : "—"}
                          </td>
                          <td><StatusBadge status={r.status} /></td>
                          <td style={{ textAlign: "right" }}>
                            {overrideTarget === r.name ? (
                              <div style={{ display: "flex", gap: "0.375rem", justifyContent: "flex-end", alignItems: "center" }}>
                                <select className="form-select" value={overrideVal}
                                  onChange={e => setOverrideVal(e.target.value)}
                                  style={{ width: "100px", height: "1.75rem", fontSize: "0.72rem", padding: "0 0.4rem" }}>
                                  <option>Present</option>
                                  <option>Late</option>
                                  <option>Absent</option>
                                </select>
                                <button className="btn btn-success btn-sm btn-icon" onClick={handleOverride}><Check size={12} /></button>
                                <button className="btn btn-ghost btn-sm btn-icon" onClick={() => setOverrideTarget(null)}><X size={12} /></button>
                              </div>
                            ) : (
                              <button className="btn btn-ghost btn-sm btn-icon"
                                onClick={() => { setOverrideTarget(r.name); setOverrideVal(r.status); }}>
                                <Edit3 size={13} />
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* ── Right: Session Summary ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div className="card">
              <div className="card-header"><div className="card-title">Session Summary</div></div>
              <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {[
                  { label: "Present", val: presentCount, cls: "badge-green", text: "#4ade80" },
                  { label: "Late",    val: lateCount,    cls: "badge-orange", text: "#fb923c" },
                  { label: "Absent",  val: absentCount,  cls: "badge-red",    text: "#f87171" },
                ].map(({ label, val, cls, text }) => (
                  <div key={label} style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    background: "var(--color-bg-elevated)", borderRadius: "0.5rem", padding: "0.625rem 0.75rem"
                  }}>
                    <span className={`badge ${cls}`}>{label}</span>
                    <span style={{ fontSize: "1.25rem", fontWeight: 800, color: text }}>{val}</span>
                    <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>/ {attendance.length || 0}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <div className="card-body">
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                  <strong>Session:</strong> {isActive
                    ? <span style={{ color: "var(--color-green)" }}>Active</span>
                    : <span style={{ color: "var(--text-muted)" }}>Idle</span>}
                </div>
                <div style={{ marginTop: "0.5rem", fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                  <strong>Total recorded:</strong> {attendance.length}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}