/**
 * API Service — Smart Classroom Manager
 * Centralised axios client. All backend calls go through here.
 * Base URL targets the FastAPI backend at port 8000.
 */
import axios from "axios";

const BASE_URL = "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
});

// ============================================================
// DASHBOARD
// ============================================================
export const getDashboardStats  = ()        => api.get("/dashboard/stats");
export const getActivityLog     = ()        => api.get("/activity-log");

// ============================================================
// STUDENTS
// ============================================================
export const getStudents        = ()        => api.get("/students");
export const deleteStudent      = (name)    => api.delete(`/students/${name}`);
export const getStudentPhoto    = (name)    => `${BASE_URL}/students/${name}/photo`;

export const registerStudent    = (formData) =>
  api.post("/register_student", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });

export const updateStudent      = (name, formData) =>
  api.put(`/students/${name}`, formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });

// ============================================================
// SESSION
// ============================================================
export const startSession       = (duration_minutes, window_minutes) =>
  api.post("/session/start", { duration_minutes, window_minutes });

export const stopSession        = ()        => api.post("/session/stop");
export const getSessionStatus   = ()        => api.get("/session/status");
export const getSessionHistory  = ()        => api.get("/session/history");
export const getSessionDetail   = (id)      => api.get(`/session/${id}`);
export const getLiveAttendance  = ()        => api.get("/session/attendance");

// ============================================================
// ATTENDANCE
// ============================================================
export const getAllAttendance    = ()        => api.get("/attendance");
export const getSessionAttendance = (id)    => api.get(`/attendance/session/${id}`);
export const overrideAttendance = (name, status) =>
  api.post("/attendance/override", { student_name: name, status });

export const exportAttendanceCSV = ()      => `${BASE_URL}/attendance/export`;

// ============================================================
// ANALYTICS
// ============================================================
export const getAttentionData   = ()        => api.get("/analytics/attention");
export const getPhoneAlerts     = ()        => api.get("/phone-alerts");
export const getSessionAnalytics = (id)    => api.get(`/analytics/session/${id}`);

// ============================================================
// IOT
// ============================================================
export const getIoTStatus       = ()        => api.get("/iot/status");
export const controlLight       = (state)   => api.post(`/iot/light/${state}`);
export const controlFan         = (state)   => api.post(`/iot/fan/${state}`);
export const setIoTMode         = (mode)    => api.post(`/iot/mode/${mode}`);

// Preserved legacy automation endpoints
export const setAutomationMode  = (mode)    => api.post(`/automation/mode/${mode}`);
export const automationOn       = ()        => api.post("/automation/on");
export const automationOff      = ()        => api.post("/automation/off");

// ============================================================
// CAMERA
// ============================================================
export const VIDEO_FEED_URL     = `${BASE_URL}/video_feed`;

export default api;
