# ============================================================
# SHARED STATE — Global in-memory state across all modules
# All hardware-facing modules read/write these variables
# ============================================================

# --- Camera / Detection ---
latest_frame = None          # Most recent video frame (numpy array)
latest_results = []          # Most recent detection boxes + names

# --- Occupancy ---
occupancy_count = 0          # Current number of detected persons

# --- Entry / Exit Logs ---
entry_logs = []              # List of {name, time} entries
exit_logs = []               # List of {name, time} exits

# --- Face Recognition ---
unknown_faces_count = 0      # Count of unrecognized faces this session

# ============================================================
# SESSION STATE (managed by SessionManager)
# ============================================================

active_session = None        # Dict with session config + state, or None

# Attendance per-student: {name -> {status, timestamp, roll_no, prn}}
session_attendance = {}

# ============================================================
# ANALYTICS STATE
# ============================================================

# Per-student attention: {name -> {score, phone_detected, last_update}}
attention_data = {}

# Recent phone detection alerts: [{name, time, confidence}]
phone_alerts = []

# ============================================================
# IOT STATE
# ============================================================

# Recent IoT activity: [{timestamp, device, action, mode}]
iot_logs = []

# ============================================================
# GENERAL ACTIVITY LOG
# ============================================================

# General activity feed for dashboard: [{timestamp, message, type}]
activity_log = []