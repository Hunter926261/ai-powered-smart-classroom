/**
 * Attention Analytics — Per-student attention, phone detection, charts.
 */
import { useState, useEffect, useCallback } from "react";
import PageHeader from "../components/PageHeader";
import { useApp } from "../context/AppContext";
import useWebSocket from "../hooks/useWebSocket";
import { getAttentionData, getSessionHistory, getSessionAnalytics } from "../services/api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid
} from "recharts";
import { Brain, Smartphone, AlertTriangle, Eye } from "lucide-react";

// Session selector button row
function SessionTabs({ sessions, selected, onSelect }) {
  return (
    <div style={{ display: "flex", gap: "0.375rem", flexWrap: "wrap", padding: "0.875rem 1.25rem", borderBottom: "1px solid var(--color-border)" }}>
      <button
        className={`btn btn-sm ${selected === "live" ? "btn-primary" : "btn-ghost"}`}
        onClick={() => onSelect("live")}
      >
        Live
      </button>
      {sessions.map((s) => (
        <button key={s._id}
          className={`btn btn-sm ${selected === s._id ? "btn-primary" : "btn-ghost"}`}
          onClick={() => onSelect(s._id)}
        >
          {s.start_time ? new Date(s.start_time).toLocaleString("en-IN", {
            month: "numeric", day: "numeric",
            hour: "2-digit", minute: "2-digit"
          }) : s._id?.slice(-6)}
        </button>
      ))}
    </div>
  );
}

export default function AttentionAnalytics() {
  const { sessionStatus } = useApp();

  const [students,       setStudents]       = useState([]);
  const [avgAttention,   setAvgAttention]   = useState(0);
  const [phoneAlerts,    setPhoneAlerts]    = useState([]);
  const [totalTracked,   setTotalTracked]   = useState(0);
  const [sessions,       setSessions]       = useState([]);
  const [selectedSession, setSelectedSession] = useState("live");
  const [loading,        setLoading]        = useState(false);

  const fetchLive = useCallback(async () => {
    try {
      const { data } = await getAttentionData();
      setStudents(data.students || []);
      setAvgAttention(data.avg_attention || 0);
      setPhoneAlerts(data.phone_alerts || []);
      setTotalTracked(data.total_tracked || 0);
    } catch { /* silent */ }
  }, []);

  const fetchSessionAnalytics = useCallback(async (id) => {
    setLoading(true);
    try {
      const { data } = await getSessionAnalytics(id);
      const rows = (data.analytics || []).map(r => ({
        name: r.student_name,
        score: r.score || 0,
        phone_detected: r.phone_detected,
        phone_count: r.phone_count || 0,
      }));
      setStudents(rows);
      const avg = rows.length ? rows.reduce((a, b) => a + b.score, 0) / rows.length : 0;
      setAvgAttention(Math.round(avg));
      setTotalTracked(rows.length);
    } catch { /* silent */ }
    setLoading(false);
  }, []);

  const fetchSessions = useCallback(async () => {
    try {
      const { data } = await getSessionHistory();
      setSessions(data.sessions || []);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    fetchSessions();
    fetchLive();
    const iv = setInterval(fetchLive, 4000);
    return () => clearInterval(iv);
  }, [fetchLive, fetchSessions]);

  useEffect(() => {
    if (selectedSession === "live") fetchLive();
    else fetchSessionAnalytics(selectedSession);
  }, [selectedSession, fetchLive, fetchSessionAnalytics]);

  // WebSocket phone alert
  useWebSocket("phone_alert", (alert) => {
    setPhoneAlerts(prev => [alert, ...prev].slice(0, 20));
  });

  const lowAttentionStudents = students.filter(s => s.score < 60);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <PageHeader title="Attention Analytics" subtitle="Post-class engagement insights" />

      <div className="page-body" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>

        {/* ── Session Selector ── */}
        <div className="card" style={{ padding: 0 }}>
          <SessionTabs sessions={sessions.slice(0, 8)} selected={selectedSession} onSelect={setSelectedSession} />
        </div>

        {/* ── Summary Stats ── */}
        <div className="grid-4">
          <div className="stat-card">
            <div className="stat-icon" style={{ background: "rgba(59,130,246,0.12)" }}>
              <Brain size={16} color="var(--color-blue)" />
            </div>
            <div className="stat-label">Avg. Attention</div>
            <div className="stat-value" style={{ color: "var(--color-blue)" }}>{avgAttention}%</div>
          </div>
          <div className="stat-card">
            <div className="stat-icon" style={{ background: "rgba(239,68,68,0.12)" }}>
              <AlertTriangle size={16} color="var(--color-red)" />
            </div>
            <div className="stat-label">Low Attention</div>
            <div className="stat-value" style={{ color: "var(--color-red)" }}>{lowAttentionStudents.length}</div>
          </div>
          <div className="stat-card">
            <div className="stat-icon" style={{ background: "rgba(249,115,22,0.12)" }}>
              <Smartphone size={16} color="var(--color-orange)" />
            </div>
            <div className="stat-label">Phone Detections</div>
            <div className="stat-value" style={{ color: "var(--color-orange)" }}>
              {phoneAlerts.length}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon" style={{ background: "rgba(168,85,247,0.12)" }}>
              <Eye size={16} color="var(--color-purple)" />
            </div>
            <div className="stat-label">Total Tracked</div>
            <div className="stat-value" style={{ color: "var(--color-purple)" }}>{totalTracked}</div>
          </div>
        </div>

        {/* ── Per Student + Chart ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>

          {/* Chart */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">Per-Student Attention</div>
              <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                Attentive when facing forward; warning if phone detected
              </span>
            </div>
            <div className="card-body">
              {students.length === 0 ? (
                <div className="empty-state">
                  <Brain size={36} />
                  <div className="empty-state-title">No analytics data available</div>
                  <div className="empty-state-sub">Start a class session to see live attention data</div>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={students} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="name" tick={{ fill: "#64748b", fontSize: 11 }} />
                    <YAxis domain={[0, 100]} tick={{ fill: "#64748b", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "0.5rem", fontSize: "0.78rem" }}
                      formatter={(val) => [`${val}%`, "Attention"]}
                    />
                    <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                      {students.map((s, i) => (
                        <Cell key={i} fill={
                          s.phone_detected ? "#ef4444"
                          : s.score >= 75 ? "#22c55e"
                          : s.score >= 50 ? "#f97316"
                          : "#ef4444"
                        } />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Student Detail List */}
          <div className="card">
            <div className="card-header"><div className="card-title">Student Breakdown</div></div>
            <div style={{ maxHeight: "300px", overflowY: "auto" }}>
              {students.length === 0 ? (
                <div className="empty-state"><div className="empty-state-sub">No data yet</div></div>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Student</th>
                      <th>Attention</th>
                      <th>Phone</th>
                    </tr>
                  </thead>
                  <tbody>
                    {students.map((s, i) => (
                      <tr key={i}>
                        <td style={{ fontWeight: 500 }}>{s.name}</td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <div style={{
                              width: "60px", height: "5px", borderRadius: "99px",
                              background: "var(--color-bg-elevated)", overflow: "hidden"
                            }}>
                              <div style={{
                                width: `${s.score}%`, height: "100%",
                                background: s.score >= 75 ? "var(--color-green)" : s.score >= 50 ? "var(--color-orange)" : "var(--color-red)"
                              }} />
                            </div>
                            <span style={{ fontSize: "0.75rem" }}>{s.score}%</span>
                          </div>
                        </td>
                        <td>
                          {s.phone_detected
                            ? <span className="badge badge-orange"><Smartphone size={10} /> {s.phone_count || 1}</span>
                            : <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>None</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>

        {/* ── Low Attention & Phone Alerts ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
          <div className="card">
            <div className="card-header">
              <div className="card-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <AlertTriangle size={14} color="var(--color-red)" /> Low Attention Students
              </div>
            </div>
            <div className="card-body">
              {lowAttentionStudents.length === 0 ? (
                <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", textAlign: "center", padding: "1rem 0" }}>
                  All students are attentive ✓
                </div>
              ) : (
                lowAttentionStudents.map((s, i) => (
                  <div key={i} style={{
                    display: "flex", justifyContent: "space-between",
                    padding: "0.5rem 0", borderBottom: "1px solid var(--color-border)",
                    fontSize: "0.8rem"
                  }}>
                    <span>{s.name}</span>
                    <span style={{ color: "var(--color-red)" }}>{s.score}%</span>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Smartphone size={14} color="var(--color-orange)" /> Phone Detection Log
              </div>
            </div>
            <div className="card-body">
              {phoneAlerts.length === 0 ? (
                <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", textAlign: "center", padding: "1rem 0" }}>
                  No phone alerts recorded
                </div>
              ) : (
                <div className="activity-log">
                  {phoneAlerts.slice(0, 6).map((a, i) => (
                    <div key={i} className="activity-item">
                      <span className="activity-time">{a.time}</span>
                      <span className="activity-msg">📱 {a.student} — confidence {Math.round((a.confidence || 0) * 100)}%</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
