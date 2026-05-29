/**
 * History — Past class sessions and reports.
 * Searchable/filterable list, drill-down detail view, export.
 */
import { useState, useEffect, useCallback } from "react";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { getSessionHistory, getSessionDetail } from "../services/api";
import { Calendar, ChevronRight, ChevronLeft, Search } from "lucide-react";

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", { year: "numeric", month: "2-digit", day: "2-digit" })
       + " " + d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
}

function SessionRow({ session, onClick }) {
  const start = session.start_time ? formatDate(session.start_time) : "—";
  const end   = session.end_time   ? formatDate(session.end_time)   : "ongoing";
  const dur   = session.duration_minutes || session.actual_duration_minutes || 60;
  return (
    <div
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center",
        padding: "0.875rem 1.25rem",
        borderBottom: "1px solid var(--color-border)",
        cursor: "pointer", transition: "background 150ms",
        gap: "1rem"
      }}
      onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.02)"}
      onMouseLeave={e => e.currentTarget.style.background = ""}
    >
      {/* Icon */}
      <div style={{
        width: "2.25rem", height: "2.25rem", borderRadius: "0.5rem",
        background: "rgba(59,130,246,0.1)", flexShrink: 0,
        display: "flex", alignItems: "center", justifyContent: "center"
      }}>
        <Calendar size={14} color="var(--color-blue)" />
      </div>

      {/* Date + duration */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: "0.85rem" }}>{start}</div>
        <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "1px" }}>
          {start} → {end} • {dur} min
        </div>
      </div>

      {/* Stats */}
      <div style={{ display: "flex", gap: "1.25rem", flexShrink: 0 }}>
        {[
          { label: "Present", val: session.present_count || 0, color: "#4ade80" },
          { label: "Late",    val: session.late_count    || 0, color: "#fb923c" },
          { label: "Absent",  val: session.absent_count  || 0, color: "#f87171" },
          { label: "Attention",val: session.avg_attention != null ? `${session.avg_attention}%` : "0%", color: "var(--color-blue)" },
        ].map(({ label, val, color }) => (
          <div key={label} style={{ textAlign: "center" }}>
            <div style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>{label}</div>
            <div style={{ fontSize: "0.95rem", fontWeight: 700, color }}>{val}</div>
          </div>
        ))}
      </div>

      <ChevronRight size={14} color="var(--text-muted)" />
    </div>
  );
}

export default function History() {
  const [sessions,  setSessions]  = useState([]);
  const [search,    setSearch]    = useState("");
  const [loading,   setLoading]   = useState(false);
  const [detail,    setDetail]    = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await getSessionHistory();
      setSessions(data.sessions || []);
    } catch { setSessions([]); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  const openDetail = async (session) => {
    setDetailLoading(true);
    setDetail({ session, attendance: [], analytics: [] });
    try {
      const { data } = await getSessionDetail(session._id);
      setDetail(data);
    } catch { /* silent */ }
    setDetailLoading(false);
  };

  const filtered = sessions.filter(s => {
    const dateStr = s.start_time || "";
    return dateStr.includes(search) ||
           String(s.present_count).includes(search);
  });

  // ── Detail View ──
  if (detail) {
    const s = detail.session || {};
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
        <PageHeader title="Session Detail" subtitle="Detailed session report" />
        <div className="page-body" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          <button className="btn btn-ghost" style={{ alignSelf: "flex-start" }} onClick={() => setDetail(null)}>
            <ChevronLeft size={14} /> Back to History
          </button>

          {/* Session meta */}
          <div className="card">
            <div className="card-header"><div className="card-title">Session Info</div></div>
            <div className="card-body" style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "1rem" }}>
              {[
                { label: "Start",    val: formatDate(s.start_time) },
                { label: "End",      val: formatDate(s.end_time) },
                { label: "Duration", val: `${s.duration_minutes || s.actual_duration_minutes || 0} min` },
                { label: "Status",   val: <StatusBadge status={s.status === "completed" ? "Idle" : "Active"} /> },
              ].map(({ label, val }) => (
                <div key={label} style={{
                  background: "var(--color-bg-elevated)", padding: "0.875rem",
                  borderRadius: "0.75rem", border: "1px solid var(--color-border)"
                }}>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>{label}</div>
                  <div style={{ fontWeight: 600, fontSize: "0.85rem" }}>{val}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Summary counts */}
          <div className="grid-4">
            {[
              { label: "Present", val: s.present_count || 0, color: "green" },
              { label: "Late",    val: s.late_count    || 0, color: "orange" },
              { label: "Absent",  val: s.absent_count  || 0, color: "red" },
              { label: "Total",   val: s.total_students || 0, color: "blue" },
            ].map(({ label, val, color }) => (
              <div key={label} className="stat-card">
                <div className="stat-label">{label}</div>
                <div className="stat-value" style={{ color: `var(--color-${color})` }}>{val}</div>
              </div>
            ))}
          </div>

          {/* Attendance table */}
          <div className="card">
            <div className="card-header"><div className="card-title">Attendance Records</div></div>
            {(detail.attendance || []).length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-sub">{detailLoading ? "Loading..." : "No attendance records"}</div>
              </div>
            ) : (
              <div className="table-container" style={{ border: "none" }}>
                <table className="data-table">
                  <thead><tr><th>Name</th><th>Roll No</th><th>Status</th><th>Time</th></tr></thead>
                  <tbody>
                    {detail.attendance.map((r, i) => (
                      <tr key={i}>
                        <td>{r.student_name}</td>
                        <td style={{ color: "var(--text-secondary)" }}>{r.roll_no}</td>
                        <td><StatusBadge status={r.status} /></td>
                        <td style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                          {r.timestamp ? new Date(r.timestamp + "Z").toLocaleTimeString() : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── List View ──
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <PageHeader title="History & Reports" subtitle="Past class sessions and reports" />

      <div className="page-body" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        <div className="card">
          <div className="card-header">
            <div className="card-title">Past Sessions ({filtered.length})</div>
            <div style={{ position: "relative" }}>
              <Search size={13} style={{ position: "absolute", left: "0.5rem", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
              <input className="form-input" placeholder="Search by date..."
                value={search} onChange={e => setSearch(e.target.value)}
                style={{ paddingLeft: "1.75rem", width: "180px", height: "2rem", fontSize: "0.78rem" }} />
            </div>
          </div>

          {loading ? (
            <div className="empty-state"><div className="empty-state-sub">Loading sessions...</div></div>
          ) : filtered.length === 0 ? (
            <div className="empty-state">
              <Calendar size={36} />
              <div className="empty-state-title">No sessions found</div>
              <div className="empty-state-sub">Start a class session to see history</div>
            </div>
          ) : (
            <div>
              {filtered.map((s, i) => (
                <SessionRow key={s._id || i} session={s} onClick={() => openDetail(s)} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
