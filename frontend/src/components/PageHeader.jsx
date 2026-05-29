/** PageHeader — Consistent top bar for every page. */
import { useApp } from "../context/AppContext";
import { Camera, Wifi, WifiOff } from "lucide-react";

export default function PageHeader({ title, subtitle }) {
  const { serverOnline, cameraOnline, wsConnected } = useApp();
  return (
    <div className="page-header">
      <div className="page-header-row">
        <div>
          <div className="page-title">{title}</div>
          {subtitle && <div className="page-subtitle">{subtitle}</div>}
        </div>
        <div className="status-bar">
          <div className="status-item">
            {wsConnected
              ? <Wifi size={12} color="#4ade80" />
              : <WifiOff size={12} color="#475569" />}
            <span style={{ color: serverOnline ? "#4ade80" : "#f87171" }}>
              {serverOnline ? "Server Online" : "Server Offline"}
            </span>
          </div>
          <div className="status-item">
            <Camera size={12} color={cameraOnline ? "#4ade80" : "#475569"} />
            <span style={{ color: cameraOnline ? "#4ade80" : "var(--text-muted)" }}>Camera</span>
          </div>
        </div>
      </div>
    </div>
  );
}
