/**
 * Student Registration — Add, edit, delete students.
 * Camera capture OR image upload. Stores face embeddings + MongoDB.
 */
import { useState, useEffect, useRef } from "react";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { getStudents, registerStudent, deleteStudent, VIDEO_FEED_URL } from "../services/api";
import { UserPlus, Trash2, Upload, Camera, User, RefreshCw } from "lucide-react";

export default function StudentRegistration() {
  const [name,    setName]    = useState("");
  const [rollNo,  setRollNo]  = useState("");
  const [prn,     setPrn]     = useState("");
  const [batch,   setBatch]   = useState("");
  const [image,   setImage]   = useState(null);
  const [preview, setPreview] = useState(null);
  const [useCamera, setUseCamera] = useState(false);
  const [message, setMessage] = useState({ text: "", ok: true });
  const [loading, setLoading] = useState(false);
  const [students, setStudents] = useState([]);
  const [studentsLoading, setStudentsLoading] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const fileRef = useRef();

  // Fetch registered students list
  const fetchStudents = async () => {
    setStudentsLoading(true);
    try {
      const { data } = await getStudents();
      setStudents(data.students || []);
    } catch {
      setStudents([]);
    } finally {
      setStudentsLoading(false);
    }
  };

  useEffect(() => { fetchStudents(); }, []);

  // Handle file selection
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setImage(file);
      setPreview(URL.createObjectURL(file));
    }
  };

  // Capture frame from live camera stream (screenshot)
  const captureFromCamera = async () => {
    try {
      // Fetch the current frame from the video_feed endpoint
      const resp = await fetch(VIDEO_FEED_URL.replace("/video_feed", "") + "/video_feed");
      // Can't snapshot MJPEG directly in browser easily; use a hidden img approach
      setMessage({ text: "Camera capture: upload a photo from the camera page instead. Or use 'Upload Photo' below.", ok: false });
    } catch {
      setMessage({ text: "Could not capture from camera.", ok: false });
    }
  };

  // Register student
  const handleRegister = async () => {
    if (!name.trim() || !rollNo.trim() || !batch || !image) {
      setMessage({ text: "Please fill all fields and select/capture a photo.", ok: false });
      return;
    }
    setLoading(true);
    setMessage({ text: "", ok: true });
    try {
      const fd = new FormData();
      fd.append("name",    name.trim());
      fd.append("batch",   batch);
      fd.append("roll_no", rollNo.trim());
      fd.append("prn",     prn.trim());
      fd.append("image",   image);

      const { data } = await registerStudent(fd);
      if (data.success) {
        setMessage({ text: data.message, ok: true });
        setName(""); setRollNo(""); setPrn(""); setBatch(""); setImage(null); setPreview(null);
        fetchStudents();
      } else {
        setMessage({ text: data.message, ok: false });
      }
    } catch (e) {
      setMessage({ text: "Registration failed. Is the backend running?", ok: false });
    } finally {
      setLoading(false);
    }
  };

  // Delete student
  const handleDelete = async (studentName) => {
    try {
      await deleteStudent(studentName);
      setDeleteConfirm(null);
      fetchStudents();
    } catch {
      setMessage({ text: "Delete failed.", ok: false });
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <PageHeader title="Student Registration" subtitle="Add and manage registered students" />

      <div className="page-body">
        <div style={{ display: "grid", gridTemplateColumns: "420px 1fr", gap: "1.25rem", alignItems: "start" }}>

          {/* ── Left: Form ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>

            {/* Student Details Card */}
            <div className="card">
              <div className="card-header">
                <div className="card-title">Student Details</div>
              </div>
              <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>

                <div className="form-group">
                  <label className="form-label">Student Name</label>
                  <input className="form-input" placeholder="e.g. Arjun Sharma"
                    value={name} onChange={e => setName(e.target.value)} />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div className="form-group">
                    <label className="form-label">Roll Number</label>
                    <input className="form-input" placeholder="e.g. CS-042"
                      value={rollNo} onChange={e => setRollNo(e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">PRN Number</label>
                    <input className="form-input" placeholder="e.g. 2021016..."
                      value={prn} onChange={e => setPrn(e.target.value)} />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Batch / Class</label>
                  <select className="form-select" value={batch} onChange={e => setBatch(e.target.value)}>
                    <option value="">Select Batch</option>
                    <option value="1">Batch 1</option>
                    <option value="2">Batch 2</option>
                    <option value="3">Batch 3</option>
                    <option value="A">Division A</option>
                    <option value="B">Division B</option>
                  </select>
                </div>

                {/* Message */}
                {message.text && (
                  <div style={{
                    padding: "0.6rem 0.875rem",
                    borderRadius: "0.5rem",
                    fontSize: "0.8rem",
                    background: message.ok ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
                    color: message.ok ? "#4ade80" : "#f87171",
                    border: `1px solid ${message.ok ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
                  }}>
                    {message.text}
                  </div>
                )}

                <button className="btn btn-primary w-full btn-lg" onClick={handleRegister} disabled={loading}>
                  {loading ? <><span className="spinner" /> Registering...</> : <><UserPlus size={16} /> Register Student</>}
                </button>
              </div>
            </div>

            {/* Camera Preview Card */}
            <div className="card">
              <div className="card-header">
                <div className="card-title">Camera Preview</div>
              </div>
              <div className="card-body">
                <div style={{
                  background: "var(--color-bg-elevated)",
                  borderRadius: "0.75rem",
                  aspectRatio: "4/3",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  overflow: "hidden",
                  border: "1px solid var(--color-border)",
                  marginBottom: "0.875rem"
                }}>
                  {preview ? (
                    <img src={preview} alt="Preview" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  ) : (
                    <div style={{ textAlign: "center", color: "var(--text-muted)" }}>
                      <Camera size={32} style={{ opacity: 0.3, marginBottom: "0.5rem" }} />
                      <div style={{ fontSize: "0.75rem" }}>Camera preview</div>
                      <div style={{ fontSize: "0.68rem" }}>Click "Start Camera" or upload a photo</div>
                    </div>
                  )}
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.625rem" }}>
                  <button className="btn btn-ghost" onClick={() => fileRef.current?.click()}>
                    <Upload size={14} /> Upload Photo
                  </button>
                  <button className="btn btn-primary" onClick={() => setUseCamera(v => !v)}>
                    <Camera size={14} /> Start Camera
                  </button>
                </div>
                <input ref={fileRef} type="file" accept="image/*" style={{ display: "none" }}
                  onChange={handleFileChange} />

                {/* Live camera stream for capture reference */}
                {useCamera && (
                  <div style={{ marginTop: "0.875rem" }}>
                    <img src={VIDEO_FEED_URL} alt="Live camera"
                      style={{ width: "100%", borderRadius: "0.5rem", border: "1px solid var(--color-border)" }} />
                    <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "0.375rem", textAlign: "center" }}>
                      Use "Upload Photo" to register from a saved screenshot
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ── Right: Student List ── */}
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">Registered Students ({students.length})</div>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={fetchStudents}>
                <RefreshCw size={12} /> Refresh
              </button>
            </div>
            <div>
              {studentsLoading ? (
                <div className="empty-state"><div style={{ color: "var(--text-muted)" }}>Loading...</div></div>
              ) : students.length === 0 ? (
                <div className="empty-state">
                  <User size={32} />
                  <div className="empty-state-title">No students registered</div>
                  <div className="empty-state-sub">Register your first student using the form</div>
                </div>
              ) : (
                <div className="table-container" style={{ border: "none" }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Roll No</th>
                        <th>PRN</th>
                        <th>Batch</th>
                        <th style={{ textAlign: "right" }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {students.map((s) => (
                        <tr key={s.name}>
                          <td>
                            <div style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
                              <div style={{
                                width: "2rem", height: "2rem",
                                borderRadius: "50%",
                                background: "var(--color-bg-elevated)",
                                border: "1px solid var(--color-border)",
                                display: "flex", alignItems: "center", justifyContent: "center",
                                fontSize: "0.75rem", fontWeight: 700,
                                color: "var(--color-blue)"
                              }}>
                                {s.name?.[0]?.toUpperCase()}
                              </div>
                              <span style={{ fontWeight: 500 }}>{s.name}</span>
                            </div>
                          </td>
                          <td style={{ color: "var(--text-secondary)" }}>{s.roll_no}</td>
                          <td style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>{s.prn || "—"}</td>
                          <td><span className="badge badge-blue">{s.batch}</span></td>
                          <td style={{ textAlign: "right" }}>
                            {deleteConfirm === s.name ? (
                              <div style={{ display: "flex", gap: "0.375rem", justifyContent: "flex-end" }}>
                                <button className="btn btn-danger btn-sm" onClick={() => handleDelete(s.name)}>Confirm</button>
                                <button className="btn btn-ghost btn-sm" onClick={() => setDeleteConfirm(null)}>Cancel</button>
                              </div>
                            ) : (
                              <button className="btn btn-ghost btn-sm btn-icon"
                                onClick={() => setDeleteConfirm(s.name)}
                                style={{ color: "var(--color-red)" }}>
                                <Trash2 size={14} />
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
        </div>
      </div>
    </div>
  );
}