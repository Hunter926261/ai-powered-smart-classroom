# ============================================================
# SHARED STATE — Global in-memory state across all modules
# All hardware-facing modules read/write these variables.
#
# Thread safety: use _state_lock for writes to mutable dicts/lists
# that are modified from background threads (async_detection).
# ============================================================

import threading

# Global lock for state modifications from background threads
_state_lock = threading.Lock()

# --- Camera / Detection ---
latest_frame = None          # Most recent video frame (numpy array)
latest_results = []          # Most recent detection boxes + names

# --- Occupancy ---
occupancy_count = 0          # Current number of detected persons

# --- Entry / Exit Logs ---
entry_logs = []              # List of {name, time} entries
exit_logs = []               # List of {name, time} exits

# --- Face Recognition ---
unknown_faces_count = 0      # Count of unrecognized faces in latest frame

# ============================================================
# SESSION STATE (managed by SessionManager)
# ============================================================

active_session = None        # Dict with session config + state, or None

# Attendance per-student: {name -> {status, timestamp, roll_no, prn}}
session_attendance = {}

# ============================================================
# ANALYTICS STATE
# ============================================================

# Per-student attention: {name -> {score, phone_detected, phone_count, last_update}}
attention_data = {}

# Per-student head pose tracking: {name -> {pitch, yaw, score (0.0-1.0)}}
head_pose_data = {}

# Per-student face visibility: {name -> {visible_frames: int, total_frames: int}}
face_visibility = {}

# Recent phone detection alerts: [{student, time, confidence}]
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