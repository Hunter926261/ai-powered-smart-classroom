/**
 * Dashboard — Overview of classroom activity.
 * Shows stats, session status, quick actions, live attendance, IoT, phone alerts, activity log.
 */
import { useNavigate } from "react-router-dom";
import { useApp } from "../context/AppContext";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import StatusBadge from "../components/StatusBadge";
import {
  Users, UserCheck, UserX, Clock, Smartphone,
  PlayCircle, UserPlus, Zap, Activity
} from "lucide-react";

function QuickAction({ label, icon: Icon, color, onClick }) {
  return (
    <button className="btn" onClick={onClick} style={{
      background: color === "blue" ? "rgba(59,130,246,0.15)" : "rgba(255,255,255,0.06)",
      color: color === "blue" ? "var(--color-blue)" : "var(--text-primary)",
      border: `1px solid ${color === "blue" ? "rgba(59,130,246,0.3)" : "var(--color-border)"}`,
      flexDirection: "column", gap: "0.375rem", padding: "0.75rem 1rem",
    }}>
      <Icon size={18} />
      <span style={{ fontSize: "0.72rem" }}>{label}</span>
    </button>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const {
    dashStats, sessionStatus,
    presentCount, lateCount, absentCount,
    occupancy, phoneAlerts, iotStatus,
  } = useApp();

  const isActive = sessionStatus === "active";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <PageHeader title="Dashboard" subtitle="Overview of today's classroom activity" />

      <div className="page-body" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>

        {/* ── Stat Cards ── */}
        <div className="grid-4">
          <StatCard
            label="Total Students"
            value={dashStats.total_students}
            sub="Registered"
            icon={Users}
            color="blue"
          />
          <StatCard
            label="Session Status"
            value={isActive ? "Active" : "Idle"}
            sub={isActive ? "Class in progress" : "No active session"}
            icon={Activity}
            color={isActive ? "green" : "gray"}
          />
          <StatCard
            label="Present"
            value={presentCount}
            sub={`Late: ${lateCount}`}
            icon={UserCheck}
            color="green"
          />
          <StatCard
            label="Absent"
            value={absentCount}
            sub="This session"
            icon={UserX}
            color="red"
          />
        </div>

        {/* ── Row 2: Quick Actions + Phone Alerts ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>

          {/* Quick Actions */}
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">Quick Actions</div>
                <div className="card-subtitle">Get started with common tasks</div>
              </div>
              <span className="badge badge-green">
                <span className="dot dot-green" /> Backend Connected
              </span>
            </div>
            <div className="card-body" style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
              <QuickAction label="Register Student" icon={UserPlus} color="blue"  onClick={() => navigate("/registration")} />
              <QuickAction label="Start New Class"  icon={PlayCircle} color="ghost" onClick={() => navigate("/start-class")} />
              <QuickAction label="View Attendance"  icon={UserCheck}  color="ghost" onClick={() => navigate("/attendance")} />
              <QuickAction label="IoT Control"      icon={Zap}        color="ghost" onClick={() => navigate("/iot")} />
            </div>
          </div>

          {/* Phone Detection Alerts */}
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <Smartphone size={14} color="var(--color-orange)" /> Phone Detection Alerts
                </div>
                <div className="card-subtitle">{phoneAlerts.length} alerts right now</div>
              </div>
              {phoneAlerts.length > 0 && (
                <span className="badge badge-orange">
                  <span className="dot dot-orange" /> {phoneAlerts.length} active
                </span>
              )}
            </div>
            <div className="card-body">
              {phoneAlerts.length === 0 ? (
                <div className="empty-state" style={{ padding: "1.5rem 1rem" }}>
                  <Smartphone size={28} />
                  <div className="empty-state-title">No phone alerts</div>
                  <div className="empty-state-sub">No phone usage detected</div>
                </div>
              ) : (
                <div className="activity-log">
                  {phoneAlerts.slice(0, 5).map((a, i) => (
                    <div key={i} className="activity-item">
                      <span className="activity-time">{a.time}</span>
                      <span className="activity-msg">📱 {a.student} — phone detected</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Row 3: Live Attendance + IoT Status ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "1rem" }}>

          {/* Live Attendance */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">Live Attendance</div>
              <button className="btn btn-ghost btn-sm" onClick={() => navigate("/attendance")}>
                View all
              </button>
            </div>
            <div className="card-body">
              {!isActive ? (
                <div className="empty-state" style={{ padding: "1.5rem 1rem" }}>
                  <Clock size={28} />
                  <div className="empty-state-title">No attendance records yet</div>
                  <div className="empty-state-sub">Start a class session to track attendance</div>
                </div>
              ) : (
                <div style={{ display: "flex", gap: "2rem", padding: "0.5rem 0" }}>
                  {[
                    { label: "Detected",  val: occupancy,    color: "var(--color-blue)" },
                    { label: "Present",   val: presentCount, color: "var(--color-green)" },
                    { label: "Late",      val: lateCount,    color: "var(--color-orange)" },
                    { label: "Absent",    val: absentCount,  color: "var(--color-red)" },
                  ].map(({ label, val, color }) => (
                    <div key={label} style={{ textAlign: "center" }}>
                      <div style={{ fontSize: "1.75rem", fontWeight: 800, color }}>{val}</div>
                      <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{label}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* IoT Status */}
          <div className="card" style={{ minWidth: "200px" }}>
            <div className="card-header">
              <div className="card-title">IoT Status</div>
              <button className="btn btn-ghost btn-sm" onClick={() => navigate("/iot")}>
                Manage
              </button>
            </div>
            <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {[
                { label: "Lights", key: "light_on" },
                { label: "Fans",   key: "fan_on" },
              ].map(({ label, key }) => (
                <div key={key} style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  background: "var(--color-bg-elevated)",
                  borderRadius: "0.5rem", padding: "0.5rem 0.75rem"
                }}>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{label}</span>
                  <StatusBadge status={iotStatus[key] ? "ON" : "OFF"} />
                </div>
              ))}
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textAlign: "center" }}>
                Mode: {iotStatus.mode}
              </div>
            </div>
          </div>
        </div>

        {/* ── Recent Activity ── */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Recent Activity</div>
          </div>
          <div className="card-body">
            {dashStats.recent_activity?.length === 0 ? (
              <div className="empty-state" style={{ padding: "1rem" }}>
                <div className="empty-state-sub">No recent activity</div>
              </div>
            ) : (
              <div className="activity-log">
                {(dashStats.recent_activity || []).map((item, i) => (
                  <div key={i} className="activity-item">
                    <span className="activity-time">{item.timestamp}</span>
                    <span className="activity-msg">{item.message}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}