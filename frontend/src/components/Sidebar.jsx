/**
 * Sidebar — Navigation for all 7 pages.
 * Highlights the active route. Preserves existing routing structure.
 */
import { NavLink, useLocation } from "react-router-dom";
import { useApp } from "../context/AppContext";
import {
  LayoutDashboard, UserPlus, Play, ClipboardList,
  Brain, Zap, History, Wifi, WifiOff, Camera
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/",            label: "Dashboard",          Icon: LayoutDashboard },
  { to: "/registration",label: "Student Registration",Icon: UserPlus },
  { to: "/start-class", label: "Start Class",         Icon: Play },
  { to: "/attendance",  label: "Attendance",          Icon: ClipboardList },
  { to: "/analytics",   label: "Attention Analytics", Icon: Brain },
  { to: "/iot",         label: "IoT Control",         Icon: Zap },
  { to: "/history",     label: "History",             Icon: History },
];

export default function Sidebar() {
  const { serverOnline, cameraOnline, wsConnected } = useApp();
  const location = useLocation();

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <div style={{
            width: "1.75rem", height: "1.75rem",
            background: "linear-gradient(135deg, #3b82f6, #6366f1)",
            borderRadius: "0.4rem",
            display: "flex", alignItems: "center", justifyContent: "center"
          }}>
            <Brain size={14} color="#fff" />
          </div>
          <div>
            <div className="sidebar-brand-name">Smart Classroom</div>
            <div className="sidebar-brand-sub">AI System</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        <div className="sidebar-section-label">Navigation</div>
        {NAV_ITEMS.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `sidebar-link${isActive ? " active" : ""}`
            }
          >
            <Icon size={15} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Status indicators at bottom */}
      <div style={{
        padding: "0.75rem 1rem",
        borderTop: "1px solid var(--color-border)",
        display: "flex",
        flexDirection: "column",
        gap: "0.4rem"
      }}>
        <div className="status-item" style={{ fontSize: "0.68rem" }}>
          {serverOnline
            ? <><span className="dot dot-green" /><span style={{ color: "#4ade80" }}>Server Online</span></>
            : <><span className="dot dot-red" /><span style={{ color: "#f87171" }}>Server Offline</span></>}
        </div>
        <div className="status-item" style={{ fontSize: "0.68rem" }}>
          <Camera size={10} color={cameraOnline ? "#4ade80" : "#475569"} />
          <span style={{ color: cameraOnline ? "#4ade80" : "var(--text-muted)", marginLeft: "0.25rem" }}>
            Camera {cameraOnline ? "Active" : "Inactive"}
          </span>
        </div>
        <div className="status-item" style={{ fontSize: "0.68rem" }}>
          {wsConnected
            ? <><Wifi size={10} color="#4ade80" /><span style={{ color: "#4ade80", marginLeft: "0.25rem" }}>WebSocket</span></>
            : <><WifiOff size={10} color="#475569" /><span style={{ color: "var(--text-muted)", marginLeft: "0.25rem" }}>WS Offline</span></>}
        </div>
      </div>
    </aside>
  );
}