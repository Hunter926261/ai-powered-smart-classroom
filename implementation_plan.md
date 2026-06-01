# Smart Classroom — Complete Architecture Audit & Migration Plan

> **Status:** Pre-implementation audit. No code has been changed.
> **Scope:** Full codebase — all backend + frontend files read and analysed.

---

## Phase 1 — Architecture Audit

### Full System Architecture Map

```
┌─────────────────────────────────────────────────────────────────┐
│                     SMART CLASSROOM SYSTEM                      │
├──────────────┬──────────────────────────────┬───────────────────┤
│ HARDWARE     │ BACKEND (FastAPI)            │ FRONTEND (React)  │
│              │                              │                   │
│ Raspberry Pi │ main.py (653 lines)          │ App.jsx           │
│ 192.168.137  │ face_manager.py              │ AppContext.jsx     │
│ .140:5000    │ attendance_manager.py        │ services/api.js   │
│ /video_feed  │ async_detection.py           │ services/socket.js│
│              │ session_manager.py           │ pages/ (7 pages)  │
│ ESP32        │ automation_manager.py        │                   │
│ 192.168.137  │ camera.py                   │ WS Client         │
│ .71          │ shared_state.py              │ ws://127.0.0.1    │
│ /light/on    │ websocket_manager.py         │ :8000/ws          │
│ /light/off   │ event_manager.py             │                   │
│ /fan/on      │ config.py + .env             │ HTTP Client       │
│ /fan/off     │ database/database.py(SQLite) │ http://127.0.0.1  │
│              │ database/mongo_client.py     │ :8000             │
│              │                              │                   │
│              │ Storage                      │                   │
│              │ attendance.db (SQLite)       │                   │
│              │ attendance.csv               │                   │
│              │ face_embeddings.pkl          │                   │
│              │ registered_faces/*.jpg       │                   │
│              │ MongoDB: students, sessions, │                   │
│              │  attendance, attention_logs, │                   │
│              │  iot_logs                    │                   │
└──────────────┴──────────────────────────────┴───────────────────┘
```

### Frontend Architecture

| Layer | File | Responsibility |
|---|---|---|
| Entry | `main.jsx` | React DOM mount |
| Root | `App.jsx` | BrowserRouter + AppProvider + routes |
| Context | `AppContext.jsx` | Global state: session, IoT, WS, dashboard stats |
| Context | `ThemeContext.jsx` | Dark/light toggle (unused in routing) |
| Hook | `useWebSocket.js` | WS event subscription (contains a broken export — see Phase 2) |
| Service | `api.js` | Axios HTTP client — hardcoded `127.0.0.1:8000` |
| Service | `socket.js` | WS singleton with auto-reconnect |
| Layout | `MainLayout.jsx` | Sidebar + content slot |
| Routes | `AppRoutes.jsx` | **DEAD FILE** — not imported anywhere |
| Pages | 7 page components | Dashboard, Registration, StartClass, Attendance, Analytics, IoT, History |
| Components | 9 components | Sidebar, StatCard, StatusBadge, PageHeader, etc. |

### Backend Architecture

| Module | File | Role |
|---|---|---|
| Server | `main.py` | FastAPI app, all 25+ HTTP routes + WS |
| Face AI | `face_manager.py` | InsightFace embed/recognize — pkl storage |
| Attendance | `attendance_manager.py` | SQLite + CSV writes (LEGACY) |
| Detection | `async_detection.py` | YOLO loop, phone detection, face recognition |
| Session | `session_manager.py` | Session lifecycle, Present/Late/Absent |
| IoT | `automation_manager.py` | ESP32 HTTP commands, AUTO/MANUAL mode |
| Camera | `camera.py` | Pi MJPEG stream reader + reconnect loop |
| State | `shared_state.py` | In-memory global state (cross-thread) |
| WS | `websocket_manager.py` | FastAPI WS broadcast manager |
| Events | `event_manager.py` | Typed WS event dispatcher |
| Config | `config.py` + `.env` | Hardware IPs, MongoDB URI, system settings |
| DB (old) | `database/database.py` | SQLite — `attendance` table only |
| DB (new) | `database/mongo_client.py` | MongoDB — all collections |

### Database Architecture (Current — Dual Write Problem)

```
SQLite  (attendance.db)
  └── attendance: id, name, batch, roll_no, date, time, status

CSV (attendance.csv)
  └── Name, Batch, RollNo, Date, Time, Status

Pickle (face_embeddings.pkl)
  └── { name: { embedding[512], batch, roll_no } }

MongoDB (smart_classroom)
  ├── students:       name, roll_no, prn, batch, photo_path, updated_at
  ├── sessions:       start_time, end_time, duration, status, counts
  ├── attendance:     session_id, student_name, roll_no, prn, status, timestamp
  ├── attention_logs: session_id, student_name, score, phone_detected, phone_count
  └── iot_logs:       timestamp, device, action, mode
```

**Target (MongoDB only):**

```
MongoDB (smart_classroom)
  ├── students:       + embeddings[], avg_embedding[], registered_at
  ├── sessions:       + avg_attention (NEW)
  ├── attendance:     unchanged schema
  ├── attention_logs: + head_pose_score, face_visible_ratio (NEW)
  └── iot_logs:       unchanged

CSV — export-only (generated on-demand, never written during operation)
```

### WebSocket Architecture

```
Backend fires:
  "recognition"  → { name, status }
  "occupancy"    → { count }
  "phone_alert"  → { time, confidence, student }

Frontend listens (socket.js singleton):
  "occupancy"   → AppContext.setOccupancy()
  "phone_alert" → AppContext.setPhoneAlerts()
  "recognition" → Attendance.jsx re-fetches attendance
  "phone_alert" → AttentionAnalytics.jsx local state
```

### Raspberry Pi Integration Flow

```
Pi (192.168.137.140:5000/video_feed)
  → camera.py → cv2.VideoCapture(PI_STREAM_URL)
    → threaded update loop with auto-reconnect
    → shared_state.latest_frame updated
  → async_detection.py → reads frames → YOLO tracking → InsightFace
  → main.py /video_feed → generate_frames() → MJPEG to browser
```

### ESP32 Integration Flow

```
ESP32 (192.168.137.71)
  Receives HTTP GET:
  /light/on, /light/off, /fan/on, /fan/off

automation_manager.py:
  AUTO mode: person_detected() → turn_on() + turn_fan_on()
  AUTO mode: auto_loop() → turn_off() after AUTO_OFF_DELAY seconds
  MANUAL mode: direct commands from frontend API calls

Frontend → /iot/light/{state}, /iot/fan/{state}, /iot/mode/{mode}
  → automation_manager methods → ESP32 HTTP GET
```

### Face Recognition Pipeline (Current)

```
Register:
  1 image → InsightFace.get() → faces[0].embedding (512-dim float)
  → stored in face_embeddings.pkl under student name
  → image saved to registered_faces/{name}.jpg

Recognize (per detection frame):
  face_crop (upper 45% of person bounding box)
  → InsightFace.get() → query embedding
  → loop all known_faces:
      distance = np.linalg.norm(query - known_embedding)
      if distance < 25: match
  → return best_match name or "Unknown"
```

### Attention Analytics Pipeline (Current — Broken)

```
Phone detected in frame
  → alert.student = first track_id with non-Unknown name (HEURISTIC)
  → attention_data[student]["score"] -= 10
  → score never recovers (monotonically decreasing)
  → NO head pose tracking
  → NO face visibility tracking
```

### Session Management Pipeline

```
POST /session/start
  → SessionManager.start_session()
  → MongoDB session document created
  → shared_state.active_session set
  → auto_end_loop thread started

During session (async_detection loop):
  → face recognized → session_manager.mark_attendance()
  → status = "Present" if elapsed <= window_minutes else "Late"
  → saved to MongoDB attendance collection

POST /session/stop
  → all unrecognized registered students → "Absent"
  → MongoDB session updated with final counts
  → shared_state.active_session = None
```

---

## Phase 2 — Issue Report

### Critical Issues (Must Fix Before Any Improvement)

| ID | File | Line | Issue | Impact |
|---|---|---|---|---|
| C1 | `database/database.py` | all | **SQLite still active** — attendance written to both SQLite and MongoDB simultaneously. Data inconsistency guaranteed. | 🔴 High |
| C2 | `face_manager.py` | 15 | `self.app.prepare(ctx_id=0)` — **hardcoded GPU**. Crashes on CPU-only machines. | 🔴 High |
| C3 | `async_detection.py` | 38 | `YOLO("yolov8n.pt").to("cuda")` — **hardcoded CUDA**. Crashes on CPU-only machines. | 🔴 High |
| C4 | `async_detection.py` | 184, 242, 315 | `asyncio.run()` from background thread — creates a new event loop each call, conflicts with FastAPI's loop. Causes `RuntimeError: This event loop is already running`. | 🔴 High |
| C5 | `face_manager.py` | all | **Single embedding per student** — one angle, one lighting. Recognition degrades significantly in real-world varied conditions. | 🔴 High |
| C6 | `face_manager.py` | 119 | **Fixed Euclidean threshold = 25** — not normalized, not adaptive. High false-positive and false-negative rate. | 🔴 High |
| C7 | `database/database.py` | 8–11 | `check_same_thread=False` on SQLite connection — multiple threads (FastAPI + async_detection) write concurrently. Causes silent data corruption. | 🔴 High |

### High-Severity Issues

| ID | File | Line | Issue | Impact |
|---|---|---|---|---|
| H1 | `attendance_manager.py` | 89–116 | CSV written on every attendance mark — `get_today_attendance_count()` reads entire CSV. Slow and fragile I/O on every request. | 🟠 Medium |
| H2 | `async_detection.py` | 286–288 | Phone alert student = **first track with non-Unknown name** — no spatial relationship to phone location. Wrong student always flagged. | 🟠 Medium |
| H3 | `async_detection.py` | 309–312 | Attention score **only ever decreases** by 10 on phone detection. No recovery. Hits 0 and stays there permanently. | 🟠 Medium |
| H4 | `AppContext.jsx` | 78–83 | Polls `/dashboard/stats` every **3s** AND `/session/status` every **2s** — even though WebSocket already fires `occupancy` events in real-time. Redundant network traffic. | 🟠 Medium |
| H5 | `Attendance.jsx` | 32–34, 38 | **Double fetch** — `setInterval(fetchAttendance, 3000)` AND `useWebSocket("recognition", fetchAttendance)` both active. Recognition events fire AND the poll fires. | 🟠 Medium |
| H6 | `session_manager.py` | 265–289 | `_auto_end_loop` — `break` inside `with self._lock` exits the inner block, not the while loop. Auto-stop logic outside the lock can trigger simultaneously. Potential double-stop / deadlock. | 🟠 Medium |
| H7 | `History.jsx` | 58 | `session.avg_attention` displayed in history list — this field is **never saved** to the MongoDB session document. Always renders `0%`. | 🟠 Medium |
| H8 | `main.py` | 337 | `GET /attendance` docstring explicitly says "from SQLite" — backed by SQLite, not MongoDB. Incorrect source after migration. | 🟠 Medium |

### Medium Issues

| ID | File | Line | Issue | Impact |
|---|---|---|---|---|
| M1 | `StudentRegistration.jsx` | 51–59 | `captureFromCamera()` is **completely non-functional** — deliberately shows an error message directing users to upload instead. | 🟡 Medium |
| M2 | `face_manager.py` | all | `face_embeddings.pkl` not protected by a thread lock — `async_detection` reads it while `/register_student` writes it. Race condition. | 🟡 Medium |
| M3 | `AppRoutes.jsx` | all | **Dead file** — not imported anywhere. `App.jsx` defines all routes directly. | 🟡 Low |
| M4 | `useWebSocket.js` | 37–43 | `useWsStatus()` uses `window.React.useState` — invalid React hook pattern. Would crash if ever called. | 🟡 Low |
| M5 | `face_manager.py` | all | **No image quality validation** — blurry, dark, overexposed, tiny-face images accepted as valid registrations. | 🟡 Medium |
| M6 | `async_detection.py` | 260–265 | `_detect_phones()` runs a **second full-frame YOLO inference** every 5th frame — same model, double GPU calls per cycle. Significant performance overhead. | 🟡 Medium |
| M7 | `StudentRegistration.jsx` | all | Only one image (front view) accepted. No multi-pose registration. | 🟡 Medium |
| M8 | `attention_data` | `shared_state.py` | Head pose **not tracked at all**. Attention score is 100% phone-detection-driven — not true engagement measurement. | 🟡 High |
| M9 | `camera.py` | 32 | `CAP_PROP_FPS` hardcoded to 30 — ignores `CAMERA_FPS` from `config.py`. | 🟡 Low |
| M10 | `main.py` | 627 | `"unknown_faces": 0` — hardcoded constant, never computed or updated. | 🟡 Low |
| M11 | `IoTControl.jsx` | 76–78 | Polls `/iot/status` every 3s — IoT state changes slowly. 3s is excessive; no WS alternative. | 🟡 Low |
| M12 | `mongo_client.py` | 62 | `prn` index: `unique=True, sparse=True` — students with empty PRN string cause upsert failures when more than one has `prn=""`. | 🟡 Medium |

### Architecture Issues

| ID | Location | Issue |
|---|---|---|
| A1 | Global | **Three storage systems in parallel**: SQLite + CSV + MongoDB. No single source of truth. |
| A2 | `shared_state.py` | `attention_data`, `phone_alerts`, `activity_log` mutated from background threads **without locks**. |
| A3 | `face_embeddings.pkl` | Pickle file not atomic — partial write on crash corrupts all embeddings. |
| A4 | `main.py` | 653-line monolith — routes, models, generators, startup logic all mixed. |
| A5 | `async_detection.py` | `FaceManager()` + `AttendanceManager()` instantiated **twice** — once in `main.py`, once in `AsyncDetection.__init__`. Two objects, doubled memory, desynchronised state. |
| A6 | Frontend | No error boundary — any thrown exception crashes the entire UI. |
| A7 | `api.js`, `socket.js` | URLs hardcoded to `127.0.0.1:8000` — not configurable via environment. |
| A8 | `mongo_client.py` | Falls back silently with no-op functions when MongoDB is down — errors are swallowed. |
| A9 | `async_detection.py` | Combine person tracking inference + phone detection into a **single YOLO call** with `classes=[0, 67]` to halve inference overhead. |

---

## Phase 3 — Migration Strategy

### Guiding Principles

1. **Hardware endpoints never change** — Pi stream URL, ESP32 IPs, HTTP command format
2. **WebSocket events preserved** — same event names and payload shapes
3. **MongoDB becomes the only database** — SQLite removed entirely
4. **CSV is export-only** — generated on-demand, never written during operation
5. **Each change is isolated** — testable independently before proceeding
6. **No breaking API contract changes** — all existing frontend URL paths preserved

### Dependency-Safe Migration Order

```
Step  1 → MongoDB hardening (mongo_client.py)
Step  2 → Remove SQLite (database.py deleted, attendance_manager.py refactored)
Step  3 → Migrate face embeddings to MongoDB (pkl removed)
Step  4 → GPU/CPU auto-detection utility
Step  5 → Fix asyncio.run() thread-safety (3 locations)
Step  6 → Fix duplicate FaceManager/AttendanceManager instantiation
Step  7 → Cosine similarity + adaptive threshold in face_manager.py
Step  8 → Image quality validation
Step  9 → Multi-pose registration (5 images) — backend endpoint
Step 10 → Head pose tracking in async_detection.py
Step 11 → Fix phone attribution (proximity-based)
Step 12 → Fix attention score formula (head_pose + visibility + phone)
Step 13 → Fix _auto_end_loop + save avg_attention on session stop
Step 14 → Add session_update + attention_update WebSocket events
Step 15 → Remove redundant polling (Attendance, AppContext)
Step 16 → Dashboard fully dynamic
Step 17 → Frontend: multi-step registration UI
Step 18 → UI redesign (CSS + new components)
```

---

## Phase 4 — Database Refactor Plan

### Files to Delete

- `backend/database/database.py` — SQLite AttendanceDatabase class
- `backend/attendance.db` — SQLite database file

### MongoDB Collections — Target Schema

```js
// students
{
  _id: ObjectId,
  name: String,
  roll_no: String,           // unique index
  prn: String,               // sparse index (NOT unique)
  batch: String,
  photo_path: String,
  embeddings: [[Float x 512]], // array of per-pose embeddings
  avg_embedding: [Float x 512], // mean of all embeddings
  registered_at: ISODate,
  updated_at: ISODate
}

// sessions
{
  _id: ObjectId,
  start_time: ISODate,
  end_time: ISODate | null,
  duration_minutes: Int,
  window_minutes: Int,
  status: "active" | "completed",
  present_count: Int,
  late_count: Int,
  absent_count: Int,
  total_students: Int,
  avg_attention: Float,        // NEW — saved on stop
  actual_duration_minutes: Int
}

// attendance (unchanged schema)
{
  _id: ObjectId,
  session_id: String,
  student_name: String,
  roll_no: String,
  prn: String,
  status: "Present" | "Late" | "Absent",
  timestamp: ISODate | null,
  overridden: Boolean
}

// attention_logs
{
  _id: ObjectId,
  session_id: String,
  student_name: String,
  score: Float,
  phone_detected: Boolean,
  phone_count: Int,
  head_pose_score: Float,     // NEW — 0.0 to 1.0
  face_visible_ratio: Float,  // NEW — 0.0 to 1.0
  last_update: ISODate
}
```

### AttendanceManager Refactor (Target)

```python
class AttendanceManager:
    """MongoDB-only. CSV is export-only."""

    def __init__(self):
        self.cooldown = 60
        self.last_marked_time = {}
        # No SQLite, no CSV file creation

    def mark_attendance(self, name, batch, roll_no):
        """Only cooldown check + shared_state update.
        Actual persistence done by SessionManager → MongoDB."""
        if name == "Unknown":
            return
        now = time.time()
        if name in self.last_marked_time:
            if now - self.last_marked_time[name] < self.cooldown:
                return
        self.last_marked_time[name] = now
        print(f"[Attendance] Mark: {name}")

    def get_attendance(self):
        """Read from MongoDB."""
        return mongo.get_all_attendance()

    def get_today_attendance_count(self):
        """MongoDB count query."""
        return mongo.count_today_attendance()
```

---

## Phase 5 — AI Accuracy Improvement Plan

### A. Hardware Auto-Detection

```python
# backend/utils/device.py  (NEW FILE)
import torch

def get_device():
    """Returns (device_str, insightface_ctx_id)"""
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        print(f"[Device] GPU: {name}")
        return "cuda", 0
    print("[Device] No GPU found — using CPU")
    return "cpu", -1
```

Apply in:
- `face_manager.py`: `self.app.prepare(ctx_id=ctx_id)`
- `async_detection.py`: `self.model = YOLO("yolov8n.pt"); self.model.to(device_str)`

### B. Multi-Pose Registration (5 Images Required)

**Required poses:** front · left · right · up · down

```python
# New backend endpoint
POST /register_student_multi
  Fields: name, roll_no, prn, batch
  Files:  front, left, right, up, down (all UploadFile)

# FaceManager.register_face_multi()
def register_face_multi(self, name, batch, roll_no, pose_frames: dict):
    embeddings = []
    for pose, frame in pose_frames.items():
        ok, issues = self.validate_image_quality(frame)
        if not ok:
            return False, f"{pose}: {'; '.join(issues)}"
        faces = self.app.get(frame)
        if not faces:
            return False, f"No face detected in {pose} image"
        embeddings.append(faces[0].embedding.tolist())

    avg_emb = np.mean(embeddings, axis=0).tolist()

    # Save to MongoDB (primary)
    mongo.upsert_student(name, roll_no, prn, batch, photo_path,
                         embeddings=embeddings, avg_embedding=avg_emb)

    # Update in-memory cache
    with self._lock:
        self.known_faces[name] = {
            "embeddings": embeddings,
            "avg_embedding": np.array(avg_emb),
            "batch": batch, "roll_no": roll_no
        }
    return True, "Registered with 5 poses"
```

### C. Image Quality Validation

```python
def validate_image_quality(self, frame, expected_pose=None):
    issues = []
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Blur (Laplacian variance — higher = sharper)
    blur = cv2.Laplacian(gray, cv2.CV_64F).var()
    if blur < 80:
        issues.append(f"Too blurry (score {blur:.0f}, need ≥80)")

    # Brightness
    brightness = gray.mean()
    if brightness < 40:
        issues.append("Too dark (increase lighting)")
    elif brightness > 230:
        issues.append("Overexposed (reduce brightness)")

    # Face detection + size check
    faces = self.app.get(frame)
    if not faces:
        issues.append("No face detected")
    else:
        box = faces[0].bbox
        face_area = (box[2]-box[0]) * (box[3]-box[1])
        frame_area = frame.shape[0] * frame.shape[1]
        if face_area / frame_area < 0.015:
            issues.append("Face too small — move closer")

        # Pose angle validation per expected_pose
        if expected_pose and hasattr(faces[0], 'pose'):
            yaw, pitch = faces[0].pose[1], faces[0].pose[0]
            pose_rules = {
                "front": (abs(yaw) < 20 and abs(pitch) < 20),
                "left":  (yaw > 20),
                "right": (yaw < -20),
                "up":    (pitch < -15),
                "down":  (pitch > 15),
            }
            if expected_pose in pose_rules and not pose_rules[expected_pose]:
                issues.append(f"Incorrect pose for {expected_pose} view")

    return len(issues) == 0, issues
```

### D. Cosine Similarity Recognition

```python
def recognize_face(self, frame):
    faces = self.app.get(frame)
    if not faces:
        return "Unknown"

    q = faces[0].embedding
    q_norm = q / (np.linalg.norm(q) + 1e-9)

    best_name = "Unknown"
    best_score = -1.0

    with self._lock:
        for name, data in self.known_faces.items():
            avg = data["avg_embedding"]
            avg_norm = avg / (np.linalg.norm(avg) + 1e-9)
            score = float(np.dot(q_norm, avg_norm))  # cosine similarity

            threshold = self.threshold.get(name, 0.45)
            if score > best_score and score >= threshold:
                best_score = score
                best_name = name

    return best_name
```

**Base cosine threshold: 0.45** (experimentally validated for InsightFace ArcFace model)

### E. Adaptive Thresholding

```python
class AdaptiveThreshold:
    BASE = 0.45

    def __init__(self):
        self._thresholds = {}  # {name: float}

    def get(self, name):
        return self._thresholds.get(name, self.BASE)

    def feedback(self, name, score, confirmed_correct):
        """Update threshold based on confirmed match feedback."""
        current = self._thresholds.get(name, self.BASE)
        if confirmed_correct and score < current:
            # Lower threshold — we were being too strict
            self._thresholds[name] = max(0.30, current - 0.02)
        elif not confirmed_correct and score >= current:
            # Raise threshold — false positive
            self._thresholds[name] = min(0.70, current + 0.02)
```

### F. Head Pose Score

```python
def head_pose_score(pitch, yaw, roll=0):
    """
    Returns 0.0–1.0: 1.0 = perfectly facing forward.
    InsightFace face.pose = [pitch, yaw, roll] in degrees.
    """
    yaw_score   = max(0.0, 1.0 - abs(yaw)   / 45.0)  # ±45° range
    pitch_score = max(0.0, 1.0 - abs(pitch) / 30.0)  # ±30° range
    return round((yaw_score + pitch_score) / 2.0, 3)
```

### G. Attention Score Formula (True Engagement Metric)

```python
def calculate_attention_score(
    head_pose_score: float,    # 0–1  (1 = looking forward)
    face_visible_ratio: float, # 0–1  (1 = face in frame always)
    phone_count: int           # cumulative phone detections this session
) -> float:
    W_POSE       = 0.40
    W_VISIBILITY = 0.35
    W_PHONE      = 0.25

    phone_penalty = min(0.50, phone_count * 0.05)  # max -50%
    phone_score = 1.0 - phone_penalty

    raw = (W_POSE * head_pose_score +
           W_VISIBILITY * face_visible_ratio +
           W_PHONE * phone_score)

    return round(max(0.0, min(100.0, raw * 100)), 1)
```

### H. Fix asyncio.run() Thread Issue

```python
# In async_detection.py — replace ALL asyncio.run() calls

# Store the event loop reference at init time
self._loop = asyncio.new_event_loop()

# Then fire events:
def _fire_event(self, event_type, data):
    asyncio.run_coroutine_threadsafe(
        event_manager.send_event(event_type, data),
        self._loop          # FastAPI's running loop
    )

# Usage:
self._fire_event("recognition", {"name": name, "status": "Present"})
self._fire_event("occupancy", {"count": new_occupancy})
self._fire_event("phone_alert", alert)
```

> **Note:** The correct pattern is to obtain FastAPI's running loop at startup
> via `asyncio.get_event_loop()` and pass it into AsyncDetection.

---

## Phase 6 — Dashboard Refactor Plan

### Problem: Hardcoded / Stale Metrics

| Metric | Current Source | Status | Target |
|---|---|---|---|
| Total Students | `face_manager.get_total_students()` | ✅ Real | MongoDB `students.count_documents()` |
| Present Today | CSV file scan | ❌ Legacy | MongoDB `attendance` today-count |
| Session Status | `session_manager.get_status()` | ✅ Real | WebSocket `session_update` |
| Present/Late/Absent | `shared_state` count | ✅ Real | WebSocket `attendance_update` |
| Occupancy | `shared_state.occupancy_count` | ✅ Real | WS `occupancy` (already done) |
| Phone Alerts | `len(shared_state.phone_alerts)` | ✅ Real | WS `phone_alert` count |
| unknown_faces | hardcoded `0` | ❌ Fake | count from track_memory |
| avg_attention | not computed | ❌ Missing | live from `attention_data` |
| avg_attention (history) | never saved | ❌ Missing | save on session stop |
| IoT Status | `automation_manager.get_status()` | ✅ Real | keep polling /iot/status |

### New WebSocket Events (Backend to Add)

```python
# Fire after every recognition / attendance mark:
"attendance_update" → {
    present: int, late: int, absent: int,
    remaining_seconds: int, session_id: str
}

# Fire every 10s during active session:
"attention_update" → {
    students: [{name, score, phone_count, head_pose_score}],
    avg_score: float
}
```

---

## Phase 7 — UI/UX Redesign Plan

### Current State

| Feature | Status |
|---|---|
| Dark theme | ✅ Implemented |
| Inter font | ✅ Imported |
| Design system (CSS vars) | ✅ Solid foundation |
| Responsive grids | ✅ Basic breakpoints |
| `.spinner` class | ❌ Missing (referenced in JSX, never defined) |
| Loading skeletons | ❌ Missing |
| Toast notifications | ❌ Missing |
| Page transitions | ❌ Missing |
| Camera capture (registration) | ❌ Broken / non-functional |
| Multi-pose registration UI | ❌ Missing |
| Attendance trend chart | ❌ Missing |
| Attention gauge | ❌ Missing |
| Head pose column | ❌ Missing |

### New Components Required

| Component | File | Purpose |
|---|---|---|
| Toast | `components/Toast.jsx` | Auto-dismiss success/error/warning |
| Skeleton | `components/Skeleton.jsx` | Loading placeholder |
| Modal | `components/Modal.jsx` | Confirmation dialogs |
| ProgressRing | `components/ProgressRing.jsx` | Circular session timer |
| PoseCapture | `components/PoseCapture.jsx` | 5-pose webcam capture |
| AttendanceTrend | `components/AttendanceTrend.jsx` | Sparkline chart (last 7 sessions) |

### Color Palette Upgrade (index.css)

```css
:root {
  /* Deeper navy backgrounds */
  --color-bg-primary:    hsl(224, 50%, 4%);
  --color-bg-secondary:  hsl(224, 44%, 7%);
  --color-bg-card:       hsl(224, 38%, 9%);
  --color-bg-elevated:   hsl(224, 32%, 13%);

  /* Indigo-violet brand */
  --color-blue:          hsl(231, 85%, 62%);
  --color-blue-glow:     hsla(231, 85%, 62%, 0.28);
  --color-accent:        hsl(262, 78%, 66%);
  --color-accent-glow:   hsla(262, 78%, 66%, 0.25);
}
```

### Registration Page Redesign — 3-Step Wizard

```
Step 1: Student Details
  Name, Roll No, PRN, Batch → validated before proceeding

Step 2: Capture 5 Poses
  Grid of 5 capture slots:
  [Front ✓] [Left  ] [Right ] [Up   ] [Down  ]
  Each slot: camera preview → Capture button → quality check → green tick
  Uses getUserMedia() browser webcam (NOT Pi stream)
  Real-time feedback: "Blurry", "Too dark", "Move closer"

Step 3: Review & Submit
  Preview all 5 captured images
  Student details summary
  Submit → POST /register_student_multi
  Success → animate to step 1, show toast
```

---

## Phase 8 — Backend Refactor Plan (File-by-File)

### [DELETE] `database/database.py`
- **Current problem:** SQLite `AttendanceDatabase` — legacy, superseded by MongoDB
- **Fix:** Delete file entirely
- **Risk:** Low — MongoDB fully replaces it
- **Dependencies:** `attendance_manager.py` (one import removed)

---

### [MODIFY] `database/mongo_client.py`
- **Current problems:**
  - `prn` unique constraint silently breaks multi-student upserts with empty PRN
  - No `get_all_attendance()`, `count_today_attendance()`, `update_student_embeddings()`
  - Comment says "SQLite fallback only"
- **Fixes:**
  - Change `prn` index from `unique=True` to non-unique sparse
  - Add `update_student_embeddings(name, embeddings, avg_embedding)`
  - Add `get_all_attendance()` with date-filtered variant
  - Add `count_today_attendance()`
  - Add `save_avg_attention_to_session(session_id, avg_attention)`
  - Remove SQLite fallback language from comments
- **Risk:** Low
- **Dependencies:** `face_manager.py`, `attendance_manager.py`, `session_manager.py`

---

### [MODIFY] `face_manager.py`
- **Current problems:** Single embedding, Euclidean distance, hardcoded GPU, no quality check, pkl storage, no thread lock
- **Fixes:**
  - Import `get_device()` from `utils/device.py` → auto ctx_id
  - Replace pkl load/save with MongoDB read/write
  - Add `threading.Lock` around `known_faces`
  - Add `register_face_multi(name, batch, roll_no, pose_frames)`
  - Add `validate_image_quality(frame, expected_pose)`
  - Replace `recognize_face()` with cosine similarity + `AdaptiveThreshold`
  - Keep `recognize_face(frame)` signature unchanged (used in async_detection)
- **Risk:** High — core recognition pipeline
- **Dependencies:** `async_detection.py`, `main.py` (registration endpoint)

---

### [MODIFY] `attendance_manager.py`
- **Current problems:** Dual-write SQLite + CSV, CSV-based count method
- **Fixes:**
  - Remove `from database.database import AttendanceDatabase`
  - Remove all CSV write logic from `mark_attendance()`
  - `get_attendance()` → `mongo.get_all_attendance()`
  - `get_today_attendance_count()` → `mongo.count_today_attendance()`
  - Keep `cooldown` and `last_marked_time` logic
- **Risk:** Medium
- **Dependencies:** `main.py` `/attendance` endpoint

---

### [MODIFY] `async_detection.py`
- **Current problems:** Hardcoded CUDA, asyncio.run() from thread, double YOLO inference, bad phone attribution, no head pose, no face visibility tracking
- **Fixes:**
  - Import `get_device()` → `self.model.to(device_str)`
  - Replace `asyncio.run()` with `asyncio.run_coroutine_threadsafe()`
  - Merge person tracking + phone detection into **one YOLO call**: `classes=[0, 67]`
  - Read `face.pose` (pitch, yaw) from InsightFace → `head_pose_score()`
  - Track `visible_frames` / `total_frames` per track_id → `face_visible_ratio`
  - Fix phone attribution: find person bounding box closest to phone box centroid
  - Feed head_pose + visibility → `calculate_attention_score()`
  - Store updated attention data in `shared_state.attention_data`
  - Remove `FaceManager()` + `AttendanceManager()` instantiation (use injected refs from main.py)
- **Risk:** High — main detection loop
- **Dependencies:** `face_manager.py`, `session_manager.py`, `shared_state.py`

---

### [MODIFY] `session_manager.py`
- **Current problems:** Buggy `_auto_end_loop`, `avg_attention` never saved
- **Fixes:**
  - Replace `while True` + `break` pattern with `threading.Event` stop signal
  - On `stop_session()`: compute `avg_attention` from `shared_state.attention_data`
  - Call `mongo.save_avg_attention_to_session(session_id, avg_attention)`
  - Fire `session_update` WebSocket event on start/stop
- **Risk:** Low-Medium
- **Dependencies:** `shared_state.py`, `mongo_client.py`

---

### [MODIFY] `shared_state.py`
- **Current problems:** No thread locks, missing head_pose_data and face_visibility
- **Fixes:**
  - Add `_lock = threading.Lock()` (used by async_detection for safe writes)
  - Add `head_pose_data = {}` — `{name: {pitch, yaw, score}}`
  - Add `face_visibility = {}` — `{name: {visible: int, total: int}}`
- **Risk:** Low-Medium
- **Dependencies:** `async_detection.py`, all readers of shared_state

---

### [MODIFY] `main.py`
- **Current problems:** 653-line monolith, `unknown_faces=0` hardcoded, duplicate manager init, legacy comments
- **Fixes:**
  - Remove duplicate `FaceManager()` + `AttendanceManager()` instantiation in `AsyncDetection.__init__` — pass existing instances via constructor
  - Fix `"unknown_faces"` — count tracks with name == "Unknown" from `shared_state.latest_results`
  - Fix `/attendance` endpoint — call `attendance_manager.get_attendance()` (now MongoDB-backed)
  - Add `POST /register_student_multi` endpoint
  - Add `GET /analytics/attention` response field: `head_pose_score`, `face_visible_ratio`
  - Optional: split into `routers/` modules (low risk refactor)
- **Risk:** Medium
- **Dependencies:** All other backend modules

---

### [NEW] `backend/utils/device.py`
- **Purpose:** Centralised GPU/CPU detection used by both FaceManager and AsyncDetection
- **Risk:** None — new utility file

---

## Phase 9 — Frontend Refactor Plan (File-by-File)

### [DELETE] `routes/AppRoutes.jsx`
- **Reason:** Dead file, not imported. Routes defined in `App.jsx`.
- **Risk:** None

---

### [MODIFY] `services/api.js`
- **Fixes:**
  - `const BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000"`
  - Add `registerStudentMulti(formData)` for 5-pose endpoint
- **Risk:** Low

---

### [MODIFY] `services/socket.js`
- **Fixes:**
  - `const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://127.0.0.1:8000/ws"`
- **Risk:** Low

---

### [MODIFY] `hooks/useWebSocket.js`
- **Fixes:**
  - Remove broken `useWsStatus` export (uses `window.React.useState`)
  - Rewrite `useWsStatus` with proper `useState` + `useEffect`
- **Risk:** Low

---

### [MODIFY] `context/AppContext.jsx`
- **Fixes:**
  - Remove `fetchSession()` polling (`setInterval 2000`) → replaced by WS `session_update`
  - Reduce `fetchStats()` to 10s interval
  - Add `socketService.on("session_update", ...)` listener
  - Add `socketService.on("attention_update", ...)` listener
  - Add `avgAttention` state variable
- **Risk:** Low-Medium

---

### [MODIFY] `pages/Attendance.jsx`
- **Fixes:**
  - Remove `setInterval(fetchAttendance, 3000)` — keep WS listener only
  - Keep `useWebSocket("recognition", fetchAttendance)` — fires on every recognition
  - One initial `fetchAttendance()` on mount
- **Risk:** Low

---

### [MODIFY] `pages/AttentionAnalytics.jsx`
- **Fixes:**
  - Remove `setInterval(fetchLive, 4000)` for live mode
  - Add `useWebSocket("attention_update", handler)` subscription
  - Add `head_pose_score` and `face_visible_ratio` columns to student table
  - Add `head_pose_score` bar to per-student chart tooltip
- **Risk:** Low

---

### [MODIFY] `pages/IoTControl.jsx`
- **Fixes:**
  - Reduce polling from 3s to 5s (IoT state rarely changes rapidly)
- **Risk:** Low (no WS alternative for IoT currently)

---

### [MODIFY] `pages/StudentRegistration.jsx`
- **Fixes:**
  - Replace single-image form with 3-step wizard
  - Step 1: text fields (name, roll_no, prn, batch)
  - Step 2: `PoseCapture` component (5 poses via `getUserMedia()`)
  - Step 3: review + submit to `POST /register_student_multi`
  - Add quality feedback display per pose
- **Risk:** Medium (significant UI change)

---

### [MODIFY] `pages/Dashboard.jsx`
- **Fixes:**
  - Receive `avgAttention` from AppContext (computed live)
  - Add attendance trend sparkline (recharts `LineChart`)
  - Fix `unknown_faces` display (from real backend data)
- **Risk:** Low

---

### [MODIFY] `index.css`
- **Fixes:**
  - Add `.spinner` keyframe animation (loading button state)
  - Upgrade color palette to HSL (deeper navy + indigo-violet brand)
  - Add `.skeleton` loading shimmer animation
  - Add `.toast` notification styles
  - Add `.progress-ring` SVG-based circular progress
  - Add `.wizard-step` styles for multi-step registration
  - Add `.pose-grid` layout for 5-pose capture
- **Risk:** Low

---

### [NEW] `components/Toast.jsx`
- Auto-dismiss success / error / warning notifications
- Portal-rendered, stacked, with slide-in animation

### [NEW] `components/Skeleton.jsx`
- Shimmer placeholders for table rows and stat cards

### [NEW] `components/PoseCapture.jsx`
- 5-slot pose capture grid using browser webcam
- getUserMedia() camera access
- Real-time quality overlay (blur score, brightness, face size)
- Green tick + thumbnail on successful capture

### [NEW] `components/ProgressRing.jsx`
- SVG circular ring for session timer
- Animates from full (session start) to empty (session end)

---

## Phase 10 — Implementation Checklist

### Pre-Implementation (Do First)

- [ ] Backup `backend/face_embeddings.pkl`
- [ ] Backup `backend/attendance.db`
- [ ] Verify MongoDB is running: `mongosh --eval "db.runCommand({ping:1})"`
- [ ] Confirm GPU availability: `python -c "import torch; print(torch.cuda.is_available())"`
- [ ] Note current working baseline (session start/stop, WS events, Pi stream, ESP32)

### Backend — Phase A: Infrastructure

- [ ] **B1** Create `backend/utils/__init__.py` and `backend/utils/device.py`
- [ ] **B2** Fix `async_detection.py` — replace `asyncio.run()` (3 locations) with `run_coroutine_threadsafe`
- [ ] **B3** Fix `async_detection.py` — replace hardcoded `"cuda"` with `device_str` from `get_device()`
- [ ] **B4** Fix `face_manager.py` — replace `ctx_id=0` with `ctx_id` from `get_device()`
- [ ] **B5** Fix `async_detection.py` — remove duplicate `FaceManager()` + `AttendanceManager()` init
- [ ] **B6** Fix `camera.py` — use `CAMERA_FPS` from config instead of hardcoded 30

### Backend — Phase B: Database Migration

- [ ] **B7** Upgrade `mongo_client.py`:
  - Remove `prn` unique constraint
  - Add `update_student_embeddings(name, embeddings, avg_embedding)`
  - Add `get_all_attendance()` and `count_today_attendance()`
  - Add `save_avg_attention_to_session(session_id, avg)`
- [ ] **B8** Rewrite `face_manager.py` — load/save from MongoDB (remove pkl)
- [ ] **B9** Run migration script: read `face_embeddings.pkl` → write to MongoDB → backup pkl
- [ ] **B10** Refactor `attendance_manager.py` — remove SQLite + CSV writes
- [ ] **B11** Delete `database/database.py`
- [ ] **B12** Delete `attendance.db`
- [ ] **B13** Fix `main.py` `/attendance` endpoint — confirm reads from MongoDB

### Backend — Phase C: AI Improvements

- [ ] **B14** Add `validate_image_quality()` to `face_manager.py`
- [ ] **B15** Add `register_face_multi()` to `face_manager.py` (5 poses)
- [ ] **B16** Replace Euclidean distance with cosine similarity in `recognize_face()`
- [ ] **B17** Add `AdaptiveThreshold` class
- [ ] **B18** Add `POST /register_student_multi` endpoint to `main.py`
- [ ] **B19** Merge YOLO person + phone detection into single call in `async_detection.py`
- [ ] **B20** Add head pose reading from `face.pose` in `async_detection.py`
- [ ] **B21** Add face visibility tracking per track_id
- [ ] **B22** Fix phone attribution — proximity-based (closest person box centroid)
- [ ] **B23** Implement `calculate_attention_score()` (head_pose + visibility + phone)
- [ ] **B24** Add `head_pose_data` + `face_visibility` to `shared_state.py`

### Backend — Phase D: Session + Events

- [ ] **B25** Fix `_auto_end_loop` with `threading.Event`
- [ ] **B26** Save `avg_attention` on `stop_session()` to MongoDB
- [ ] **B27** Add `session_update` WebSocket event (fire on start + stop)
- [ ] **B28** Add `attention_update` WebSocket event (fire every 10s during session)
- [ ] **B29** Fix `"unknown_faces": 0` — compute from `shared_state.latest_results`

### Frontend — Phase A: Foundations

- [ ] **F1** Create `frontend/.env` with `VITE_API_URL` + `VITE_WS_URL`
- [ ] **F2** Update `api.js` to use `import.meta.env.VITE_API_URL`
- [ ] **F3** Update `socket.js` to use `import.meta.env.VITE_WS_URL`
- [ ] **F4** Fix `useWebSocket.js` — remove broken `useWsStatus`, rewrite correctly
- [ ] **F5** Delete `routes/AppRoutes.jsx`
- [ ] **F6** Add `.spinner`, `.skeleton`, `.toast`, `.wizard-step`, `.pose-grid` to `index.css`
- [ ] **F7** Upgrade `index.css` color palette to HSL

### Frontend — Phase B: Context + Data Flow

- [ ] **F8** `AppContext.jsx` — remove `fetchSession` 2s poll → WS `session_update`
- [ ] **F9** `AppContext.jsx` — reduce `fetchStats` to 10s
- [ ] **F10** `AppContext.jsx` — add `attention_update` WS listener, add `avgAttention` state

### Frontend — Phase C: Page Fixes

- [ ] **F11** `Attendance.jsx` — remove 3s polling interval, keep WS listener only
- [ ] **F12** `AttentionAnalytics.jsx` — replace 4s poll with WS `attention_update`
- [ ] **F13** `AttentionAnalytics.jsx` — add head_pose_score + face_visible_ratio columns
- [ ] **F14** `IoTControl.jsx` — reduce polling to 5s
- [ ] **F15** `Dashboard.jsx` — add avg_attention stat card, fix unknown_faces

### Frontend — Phase D: Registration Redesign

- [ ] **F16** Create `components/PoseCapture.jsx` (getUserMedia + 5 slots)
- [ ] **F17** Create `components/Toast.jsx`
- [ ] **F18** Create `components/Skeleton.jsx`
- [ ] **F19** Create `components/ProgressRing.jsx`
- [ ] **F20** Rewrite `StudentRegistration.jsx` — 3-step wizard

### Verification

- [ ] Backend starts without error: `uvicorn main:app --reload --port 8000`
- [ ] Pi stream visible at `/video_feed`
- [ ] ESP32 `/light/on`, `/light/off`, `/fan/on`, `/fan/off` respond correctly
- [ ] Face registration works with 5 poses — quality validation triggers correctly
- [ ] Cosine similarity recognition identifies registered students accurately
- [ ] Session start → Present/Late marking → session stop → Absent computed
- [ ] MongoDB `sessions` collection has `avg_attention` after stop
- [ ] `attendance.db` and `face_embeddings.pkl` no longer written to
- [ ] CSV export downloads correct data from MongoDB
- [ ] Dashboard shows no hardcoded values
- [ ] WebSocket events fire: `occupancy`, `recognition`, `phone_alert`, `session_update`, `attention_update`
- [ ] No `asyncio` runtime errors in backend logs
- [ ] App runs on CPU-only machine without crash

---

## Open Questions (Require Your Decision Before Implementation)

> [!IMPORTANT]
> **Q1 — 5-Pose Camera Source:** Should the registration webcam use:
> - **(A) Browser getUserMedia()** — laptop webcam, student at registration terminal *(recommended)*
> - **(B) Raspberry Pi stream** — student sits at desk for each pose
>
> Option A is recommended: gives direct quality control and pose validation.

> [!IMPORTANT]
> **Q2 — Existing Student Migration:** Students exist in `face_embeddings.pkl` with single embeddings. Should they:
> - **(A)** Be auto-migrated to MongoDB with single embedding as `avg_embedding` *(recommended — continuity)*
> - **(B)** Be deleted — require re-registration with 5 poses
> - **(C)** Be kept in pkl as-is until re-registered

> [!IMPORTANT]
> **Q3 — Batch Options:** The batch dropdown (`1, 2, 3, A, B`) is hardcoded. Should it be:
> - **(A)** Kept hardcoded *(simplest)*
> - **(B)** Made configurable from a settings page or `.env` file

> [!NOTE]
> **Q4 — Attention Score Weights:** Proposed: Head Pose 40% · Face Visibility 35% · Phone 25%.
> Should these weights be adjusted to match your classroom policy?

> [!NOTE]
> **Q5 — IoT WebSocket:** Should a `iot_update` WebSocket event be added so
> `IoTControl.jsx` can eliminate polling entirely? (Minor backend addition.)
