/**
 * IoT Control — Manage classroom lights and fans.
 * Auto mode based on occupancy. Manual overrides. Activity log.
 * !! ESP32 commands preserved via API layer !!
 */
import { useState, useEffect, useCallback } from "react";
import PageHeader from "../components/PageHeader";
import { useApp } from "../context/AppContext";
import { getIoTStatus, controlLight, controlFan, setIoTMode } from "../services/api";
import { Lightbulb, Wind, Zap, RefreshCw } from "lucide-react";

// Toggle Switch Component
function Toggle({ checked, onChange, disabled }) {
  return (
    <label className="toggle" style={{ cursor: disabled ? "not-allowed" : "pointer" }}>
      <input type="checkbox" checked={checked} onChange={onChange} disabled={disabled} />
      <div className="toggle-track">
        <div className="toggle-thumb" />
      </div>
    </label>
  );
}

// Device Card Component
function DeviceCard({ icon: Icon, name, sub, isOn, onToggle, manualMode, iconColor, iconBg }) {
  return (
    <div className={`device-card ${isOn ? "on-state" : ""}`}>
      <div className="device-card-header">
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div className="device-icon" style={{ background: iconBg }}>
            <Icon size={18} color={iconColor} />
          </div>
          <div>
            <div className="device-name">{name}</div>
            <div className="device-sub">{sub}</div>
          </div>
        </div>
        <span className={`badge ${isOn ? "badge-blue" : "badge-gray"}`}>
          {isOn ? "ON" : "OFF"}
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
          Manual Control
        </span>
        <div className="toggle-wrap">
          <Toggle checked={isOn} onChange={onToggle} disabled={!manualMode} />
        </div>
      </div>

      {!manualMode && (
        <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", textAlign: "center" }}>
          Switch to Manual mode to override
        </div>
      )}
    </div>
  );
}

export default function IoTControl() {
  const { iotStatus: ctxIoT, setIotStatus } = useApp();

  const [status,   setStatus]   = useState({ mode: "AUTO", light_on: false, fan_on: false, recent_logs: [], auto_off_delay: 30 });
  const [loading,  setLoading]  = useState({});

  const fetchStatus = useCallback(async () => {
    try {
      const { data } = await getIoTStatus();
      setStatus(data);
      setIotStatus(data);
    } catch { /* silent */ }
  }, [setIotStatus]);

  useEffect(() => {
    fetchStatus();
    const iv = setInterval(fetchStatus, 5000); // 5s — IoT state changes slowly
    return () => clearInterval(iv);
  }, [fetchStatus]);

  const setLoad = (key, val) => setLoading(p => ({ ...p, [key]: val }));

  const handleMode = async (mode) => {
    setLoad("mode", true);
    try {
      await setIoTMode(mode);
      setStatus(s => ({ ...s, mode }));
    } finally { setLoad("mode", false); }
  };

  const handleLight = async () => {
    if (status.mode !== "MANUAL") return;
    const newState = !status.light_on;
    setLoad("light", true);
    try {
      await controlLight(newState ? "on" : "off");
      setStatus(s => ({ ...s, light_on: newState }));
      fetchStatus();
    } finally { setLoad("light", false); }
  };

  const handleFan = async () => {
    if (status.mode !== "MANUAL") return;
    const newState = !status.fan_on;
    setLoad("fan", true);
    try {
      await controlFan(newState ? "on" : "off");
      setStatus(s => ({ ...s, fan_on: newState }));
      fetchStatus();
    } finally { setLoad("fan", false); }
  };

  const isManual = status.mode === "MANUAL";
  const logs = status.recent_logs || [];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <PageHeader title="IoT Control" subtitle="Manage classroom lights and fans" />

      <div className="page-body" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>

        {/* ── Auto Mode Banner ── */}
        <div className="card">
          <div className="card-body" style={{
            display: "flex", alignItems: "center", justifyContent: "space-between"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.875rem" }}>
              <div style={{
                width: "2.5rem", height: "2.5rem", borderRadius: "0.75rem",
                background: "rgba(249,115,22,0.12)",
                display: "flex", alignItems: "center", justifyContent: "center"
              }}>
                <Zap size={18} color="var(--color-orange)" />
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>Auto Mode</div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                  Automatically toggles devices based on person detection
                </div>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "0.875rem" }}>
              {/* Mode badge */}
              <span className={`badge ${isManual ? "badge-orange" : "badge-green"}`}>
                {isManual ? "No Person" : "Auto Active"}
              </span>

              {/* Mode toggle */}
              <div style={{ display: "flex", gap: "0.375rem" }}>
                <button
                  className={`btn btn-sm ${!isManual ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => handleMode("AUTO")}
                  disabled={loading.mode}
                >
                  AUTO
                </button>
                <button
                  className={`btn btn-sm ${isManual ? "" : "btn-ghost"}`}
                  onClick={() => handleMode("MANUAL")}
                  disabled={loading.mode}
                  style={isManual ? { background: "var(--color-orange)", color: "#fff" } : {}}
                >
                  MANUAL
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* ── Device Cards ── */}
        <div className="grid-2">
          <DeviceCard
            icon={Lightbulb}
            name="Classroom Lights"
            sub="Ceiling lights × 4"
            isOn={status.light_on}
            onToggle={handleLight}
            manualMode={isManual}
            iconColor={status.light_on ? "#facc15" : "#64748b"}
            iconBg={status.light_on ? "rgba(234,179,8,0.15)" : "rgba(148,163,184,0.08)"}
          />
          <DeviceCard
            icon={Wind}
            name="Classroom Fans"
            sub="Ceiling fans × 2"
            isOn={status.fan_on}
            onToggle={handleFan}
            manualMode={isManual}
            iconColor={status.fan_on ? "var(--color-blue)" : "#64748b"}
            iconBg={status.fan_on ? "rgba(59,130,246,0.12)" : "rgba(148,163,184,0.08)"}
          />
        </div>

        {/* ── Automation Logic Info ── */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Automation Logic</div>
          </div>
          <div className="card-body" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.875rem" }}>
            <div style={{
              background: "var(--color-bg-elevated)", borderRadius: "0.75rem",
              padding: "0.875rem", border: "1px solid var(--color-border)"
            }}>
              <div style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--color-red)", marginBottom: "0.375rem" }}>
                🔴 No Person Detected
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                → Automatically turn OFF fans and lights after {status.auto_off_delay ?? 30} seconds
              </div>
            </div>
            <div style={{
              background: "var(--color-bg-elevated)", borderRadius: "0.75rem",
              padding: "0.875rem", border: "1px solid var(--color-border)"
            }}>
              <div style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--color-green)", marginBottom: "0.375rem" }}>
                🟢 Person Detected
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                → Automatically turn ON fans and lights immediately
              </div>
            </div>
          </div>
        </div>

        {/* ── Recent Activity ── */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Recent Activity</div>
            <button className="btn btn-ghost btn-sm" onClick={fetchStatus}>
              <RefreshCw size={12} /> Refresh
            </button>
          </div>
          <div className="card-body">
            {logs.length === 0 ? (
              <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", textAlign: "center", padding: "0.5rem 0" }}>
                No recent activity
              </div>
            ) : (
              <div className="activity-log">
                {logs.slice(0, 10).map((log, i) => (
                  <div key={i} className="activity-item">
                    <span className="activity-time">{log.timestamp}</span>
                    <span className="activity-msg">
                      <span style={{ color: log.mode === "AUTO" ? "var(--color-blue)" : "var(--color-orange)" }}>
                        {log.mode === "AUTO" ? "Auto" : "Manual"}
                      </span>
                      {" "}{log.device} turned{" "}
                      <span style={{ color: log.action === "ON" ? "var(--color-green)" : "var(--color-red)" }}>
                        {log.action}
                      </span>
                    </span>
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
