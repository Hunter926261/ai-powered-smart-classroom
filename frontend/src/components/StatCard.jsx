/** StatCard — Reusable metric display card. */
export default function StatCard({ label, value, sub, icon: Icon, color = "blue", glow = true }) {
  const colorMap = {
    blue:   { text: "var(--color-blue)",   bg: "rgba(59,130,246,0.12)",  glowBg: "rgba(59,130,246,0.2)"  },
    green:  { text: "var(--color-green)",  bg: "rgba(34,197,94,0.12)",   glowBg: "rgba(34,197,94,0.2)"   },
    orange: { text: "var(--color-orange)", bg: "rgba(249,115,22,0.12)",  glowBg: "rgba(249,115,22,0.2)"  },
    red:    { text: "var(--color-red)",    bg: "rgba(239,68,68,0.12)",   glowBg: "rgba(239,68,68,0.2)"   },
    purple: { text: "var(--color-purple)", bg: "rgba(168,85,247,0.12)",  glowBg: "rgba(168,85,247,0.2)"  },
    cyan:   { text: "var(--color-cyan)",   bg: "rgba(6,182,212,0.12)",   glowBg: "rgba(6,182,212,0.2)"   },
    gray:   { text: "var(--text-muted)",   bg: "rgba(148,163,184,0.08)", glowBg: "rgba(148,163,184,0.1)" },
  };
  const c = colorMap[color] || colorMap.blue;

  return (
    <div className="stat-card">
      {glow && (
        <div className="stat-card-glow" style={{ background: c.glowBg, top: -10, right: -10 }} />
      )}
      {Icon && (
        <div className="stat-icon" style={{ background: c.bg }}>
          <Icon size={16} color={c.text} />
        </div>
      )}
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ color: c.text }}>{value ?? "—"}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}