/** StatusBadge — Coloured status chip for Present/Late/Absent/Active/Idle */
export default function StatusBadge({ status }) {
  const map = {
    Present: "badge-green",
    Late:    "badge-orange",
    Absent:  "badge-red",
    Active:  "badge-green",
    active:  "badge-green",
    Idle:    "badge-gray",
    idle:    "badge-gray",
    Online:  "badge-blue",
    Offline: "badge-red",
    ON:      "badge-green",
    OFF:     "badge-gray",
  };
  const cls = map[status] || "badge-gray";
  return <span className={`badge ${cls}`}>{status}</span>;
}
