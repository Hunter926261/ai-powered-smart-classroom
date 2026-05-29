"""
Smart Classroom Manager — FastAPI Backend
==========================================
Main application entry point.

!! HARDWARE CRITICAL — PRESERVED SETTINGS !!
  - Camera stream: http://192.168.137.140:5000/video_feed  (config.py)
  - ESP32 IP: 192.168.137.71                               (config.py)
  - /video_feed endpoint preserved exactly
  - /register_student endpoint preserved + extended (prn field added)
  - /automation/* endpoints preserved exactly
  - /attendance endpoint preserved exactly
"""

import io
import os
import csv
import time
import asyncio
from datetime import datetime

import cv2
import numpy as np
from fastapi import FastAPI, Form, WebSocket, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ---- Core Modules (PRESERVED) ----
from face_manager import FaceManager
from attendance_manager import AttendanceManager
from camera import Camera
from async_detection import AsyncDetection
import shared_state
from websocket_manager import manager
from automation_manager import automation_manager

# ---- New Modules ----
from session_manager import SessionManager
from database.mongo_client import mongo

# ============================================================
# APP INIT
# ============================================================

app = FastAPI(title="Smart Classroom Manager API", version="2.0")

# CORS — allow all origins for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# MANAGER INITIALIZATION
# ============================================================

face_manager = FaceManager()
attendance_manager = AttendanceManager()
camera = Camera()
detector = AsyncDetection(camera)

# Wire managers into detector (PRESERVED)
detector.face_manager = face_manager
detector.attendance_manager = attendance_manager

# Initialize session manager with face_manager reference
_session_manager = SessionManager(face_manager)
detector.session_manager = _session_manager

# ============================================================
# REQUEST MODELS
# ============================================================

class StudentRequest(BaseModel):
    name: str

class SessionStartRequest(BaseModel):
    duration_minutes: int = 60
    window_minutes: int = 10

class AttendanceOverrideRequest(BaseModel):
    student_name: str
    status: str  # "Present" | "Late" | "Absent"

class IoTCommandRequest(BaseModel):
    device: str   # "light" | "fan"
    state: str    # "on" | "off"


# ============================================================
# !! PRESERVED: WEBSOCKET ROUTE !!
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except:
        manager.disconnect(websocket)


# ============================================================
# !! PRESERVED: VIDEO FEED ROUTE !!
# ============================================================

def generate_frames():
    """Generate MJPEG stream from latest detection frame."""
    while True:
        # !! PRESERVED: Shared state access !!
        frame = shared_state.latest_frame
        detections = shared_state.latest_results

        if frame is None:
            continue

        stream_frame = frame.copy()

        # !! PRESERVED: Draw detection boxes !!
        for det in detections:
            x1, y1, x2, y2 = det["box"]
            track_id = det["id"]
            name = det["name"]

            cv2.rectangle(stream_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                stream_frame,
                f"{name} ({track_id})",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

        # !! PRESERVED: FPS overlay !!
        cv2.putText(
            stream_frame,
            f"Camera FPS: {camera.fps}",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            2
        )

        _, buffer = cv2.imencode(".jpg", stream_frame)
        frame_bytes = buffer.tobytes()

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' +
            frame_bytes +
            b'\r\n'
        )

        time.sleep(0.03)


@app.get("/video_feed")
def video_feed():
    """!! PRESERVED: Live MJPEG camera stream !!"""
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ============================================================
# !! PRESERVED + EXTENDED: STUDENT REGISTRATION !!
# ============================================================

@app.post("/register_student")
async def register_student(
    name: str = Form(...),
    batch: str = Form(...),
    roll_no: str = Form(...),
    prn: str = Form(""),          # NEW: PRN field (optional for backward compat)
    image: UploadFile = File(...)
):
    """Register a student with face embedding. Preserved + adds PRN + MongoDB."""
    try:
        image_bytes = await image.read()
        np_array = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

        if frame is None:
            return {"success": False, "message": "Invalid image"}

        success = detector.face_manager.register_face(name, batch, roll_no, frame)

        if success:
            # NEW: Also persist to MongoDB
            photo_path = f"registered_faces/{name}.jpg"
            mongo.upsert_student(name, roll_no, prn, batch, photo_path)

            # Log activity
            shared_state.activity_log.insert(0, {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "message": f"Student {name} registered",
                "type": "registration"
            })

            return {"success": True, "message": f"{name} registered successfully"}

        return {"success": False, "message": "Face not detected in image"}

    except Exception as e:
        return {"success": False, "message": str(e)}


# ============================================================
# STUDENT MANAGEMENT (NEW)
# ============================================================

@app.get("/students")
def get_students():
    """Get all registered students (from face_manager + MongoDB)."""
    students = face_manager.get_all_students()
    # Enrich with PRN from MongoDB if available
    mongo_students = {s["roll_no"]: s for s in mongo.get_all_students()}
    for student in students:
        roll_no = student.get("roll_no", "")
        if roll_no in mongo_students:
            student["prn"] = mongo_students[roll_no].get("prn", "")
            student["photo_path"] = mongo_students[roll_no].get("photo_path", "")
        else:
            student["prn"] = ""
            student["photo_path"] = ""
    return {"students": students, "total": len(students)}


@app.delete("/students/{name}")
def delete_student(name: str):
    """Delete a registered student by name."""
    try:
        if name not in face_manager.known_faces:
            raise HTTPException(status_code=404, detail="Student not found")

        student_info = face_manager.known_faces[name]
        roll_no = student_info.get("roll_no", "")

        # Remove from face embeddings
        del face_manager.known_faces[name]
        face_manager.save_faces()

        # Remove face image
        photo_path = f"registered_faces/{name}.jpg"
        if os.path.exists(photo_path):
            os.remove(photo_path)

        # Remove from MongoDB
        mongo.delete_student(roll_no)

        shared_state.activity_log.insert(0, {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "message": f"Student {name} deleted",
            "type": "registration"
        })

        return {"success": True, "message": f"{name} deleted"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/students/{name}")
async def update_student(
    name: str,
    new_name: str = Form(...),
    batch: str = Form(...),
    roll_no: str = Form(...),
    prn: str = Form(""),
    image: UploadFile = File(None)
):
    """Update student info. Optionally re-register face photo."""
    try:
        if name not in face_manager.known_faces:
            raise HTTPException(status_code=404, detail="Student not found")

        # Update face_manager
        old_data = face_manager.known_faces[name]
        face_manager.known_faces[new_name] = {
            "embedding": old_data["embedding"],
            "batch": batch,
            "roll_no": roll_no,
            "prn": prn
        }

        if new_name != name:
            del face_manager.known_faces[name]

        # Re-register face if new image provided
        if image:
            image_bytes = await image.read()
            np_array = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
            if frame is not None:
                face_manager.register_face(new_name, batch, roll_no, frame)

        face_manager.save_faces()

        # Update MongoDB
        photo_path = f"registered_faces/{new_name}.jpg"
        mongo.upsert_student(new_name, roll_no, prn, batch, photo_path)

        return {"success": True, "message": f"Student updated"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/students/{name}/photo")
def get_student_photo(name: str):
    """Serve registered face photo."""
    path = f"registered_faces/{name}.jpg"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Photo not found")
    return StreamingResponse(open(path, "rb"), media_type="image/jpeg")


# ============================================================
# !! PRESERVED: ATTENDANCE API !!
# ============================================================

@app.get("/attendance")
async def get_attendance():
    """!! PRESERVED: Get all attendance records from SQLite !!"""
    data = attendance_manager.get_attendance()
    return {"attendance": data}


@app.get("/attendance/session/{session_id}")
def get_session_attendance(session_id: str):
    """Get attendance records for a specific session from MongoDB."""
    records = mongo.get_session_attendance(session_id)
    return {"attendance": records, "session_id": session_id}


@app.post("/attendance/override")
def override_attendance(req: AttendanceOverrideRequest):
    """Faculty manual override of attendance status."""
    if req.status not in ("Present", "Late", "Absent"):
        raise HTTPException(status_code=400, detail="Invalid status")

    if req.student_name in shared_state.session_attendance:
        shared_state.session_attendance[req.student_name]["status"] = req.status
        shared_state.session_attendance[req.student_name]["overridden"] = True

        # Update MongoDB if session is active
        if shared_state.active_session:
            session_id = shared_state.active_session.get("session_id", "")
            if session_id:
                rec = shared_state.session_attendance[req.student_name]
                mongo.save_attendance_record(
                    session_id,
                    req.student_name,
                    rec.get("roll_no", ""),
                    rec.get("prn", ""),
                    req.status,
                    rec.get("timestamp")
                )

        shared_state.activity_log.insert(0, {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "message": f"Override: {req.student_name} → {req.status}",
            "type": "override"
        })

        return {"success": True}

    raise HTTPException(status_code=404, detail="Student not found in current session")


@app.get("/attendance/export")
def export_attendance_csv():
    """Export current session attendance as CSV download."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["Name", "RollNo", "PRN", "Status", "Timestamp"]
    )
    writer.writeheader()

    for name, rec in shared_state.session_attendance.items():
        writer.writerow({
            "Name": name,
            "RollNo": rec.get("roll_no", ""),
            "PRN": rec.get("prn", ""),
            "Status": rec.get("status", ""),
            "Timestamp": rec.get("timestamp", "")
        })

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance.csv"}
    )


# ============================================================
# SESSION MANAGEMENT (NEW)
# ============================================================

@app.post("/session/start")
def start_session(req: SessionStartRequest):
    """Start a new class session."""
    try:
        session = _session_manager.start_session(
            req.duration_minutes,
            req.window_minutes
        )
        return {"success": True, "session": session}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/session/stop")
def stop_session():
    """Stop the current session and compute final attendance."""
    try:
        summary = _session_manager.stop_session()
        return {"success": True, "summary": summary}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/session/status")
def session_status():
    """Get current session status with timer and live counts."""
    return _session_manager.get_status()


@app.get("/session/attendance")
def live_session_attendance():
    """Get all attendance records for the current session."""
    records = []
    for name, rec in shared_state.session_attendance.items():
        records.append({
            "name": name,
            "roll_no": rec.get("roll_no", ""),
            "prn": rec.get("prn", ""),
            "status": rec.get("status", ""),
            "timestamp": rec.get("timestamp", ""),
            "overridden": rec.get("overridden", False)
        })
    return {"attendance": records}


@app.get("/session/history")
def session_history():
    """Get all past sessions from MongoDB."""
    sessions = mongo.get_all_sessions()
    return {"sessions": sessions, "total": len(sessions)}


@app.get("/session/{session_id}")
def get_session_detail(session_id: str):
    """Get detailed info for a past session."""
    session = mongo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    attendance = mongo.get_session_attendance(session_id)
    analytics = mongo.get_session_analytics(session_id)
    return {
        "session": session,
        "attendance": attendance,
        "analytics": analytics
    }


# ============================================================
# !! PRESERVED: AUTOMATION / IOT APIs !!
# ============================================================

@app.post("/automation/mode/{mode}")
def set_mode(mode: str):
    """!! PRESERVED: Set automation mode !!"""
    automation_manager.set_mode(mode)
    return {"status": "success", "mode": mode}


@app.post("/automation/on")
def manual_on():
    """!! PRESERVED: Manual light ON !!"""
    automation_manager.manual_on()
    return {"status": "light_on"}


@app.post("/automation/off")
def manual_off():
    """!! PRESERVED: Manual light OFF !!"""
    automation_manager.manual_off()
    return {"status": "light_off"}


# ============================================================
# IOT STATUS + DEVICE CONTROL (NEW)
# ============================================================

@app.get("/iot/status")
def iot_status():
    """Get current IoT device states and recent activity."""
    return automation_manager.get_status()


@app.post("/iot/light/{state}")
def control_light(state: str):
    """Control classroom lights. state = 'on' | 'off'"""
    if state == "on":
        automation_manager.manual_on()
        return {"success": True, "light": "on"}
    elif state == "off":
        automation_manager.manual_off()
        return {"success": True, "light": "off"}
    raise HTTPException(status_code=400, detail="state must be 'on' or 'off'")


@app.post("/iot/fan/{state}")
def control_fan(state: str):
    """Control classroom fans. state = 'on' | 'off'"""
    if state == "on":
        automation_manager.manual_fan_on()
        return {"success": True, "fan": "on"}
    elif state == "off":
        automation_manager.manual_fan_off()
        return {"success": True, "fan": "off"}
    raise HTTPException(status_code=400, detail="state must be 'on' or 'off'")


@app.post("/iot/mode/{mode}")
def iot_mode(mode: str):
    """Set IoT automation mode: AUTO or MANUAL."""
    if mode not in ("AUTO", "MANUAL"):
        raise HTTPException(status_code=400, detail="mode must be AUTO or MANUAL")
    automation_manager.set_mode(mode)
    return {"success": True, "mode": mode}


# ============================================================
# ANALYTICS (NEW)
# ============================================================

@app.get("/analytics")
async def analytics():
    """!! PRESERVED: Base analytics endpoint !!"""
    return {
        "occupancy": shared_state.occupancy_count,
        "entries": shared_state.entry_logs[-10:],
        "exits": shared_state.exit_logs[-10:]
    }


@app.get("/analytics/attention")
def get_attention():
    """Get live attention data for all tracked students."""
    result = []
    for name, data in shared_state.attention_data.items():
        result.append({
            "name": name,
            "score": data.get("score", 100),
            "phone_detected": data.get("phone_detected", False),
            "phone_count": data.get("phone_count", 0),
            "last_update": data.get("last_update", "")
        })
    avg_score = (
        sum(r["score"] for r in result) / len(result)
        if result else 0
    )
    return {
        "students": result,
        "avg_attention": round(avg_score, 1),
        "total_tracked": len(result),
        "phone_alerts": shared_state.phone_alerts[:10]
    }


@app.get("/analytics/session/{session_id}")
def session_analytics(session_id: str):
    """Get attention analytics for a past session."""
    return {"analytics": mongo.get_session_analytics(session_id)}


@app.get("/phone-alerts")
def phone_alerts():
    """Get recent phone detection alerts."""
    return {"alerts": shared_state.phone_alerts[:20]}


# ============================================================
# DASHBOARD & ACTIVITY
# ============================================================

@app.get("/dashboard/stats")
def dashboard_stats():
    """!! PRESERVED + ENHANCED: Dashboard statistics !!"""
    session_status = _session_manager.get_status()

    present_count = sum(
        1 for r in shared_state.session_attendance.values()
        if r["status"] == "Present"
    )
    late_count = sum(
        1 for r in shared_state.session_attendance.values()
        if r["status"] == "Late"
    )
    absent_count = sum(
        1 for r in shared_state.session_attendance.values()
        if r["status"] == "Absent"
    )

    return {
        # Preserved fields
        "total_students": detector.face_manager.get_total_students(),
        "present_today": detector.attendance_manager.get_today_attendance_count(),
        "active_cameras": 1 if shared_state.latest_frame is not None else 0,
        "unknown_faces": 0,

        # New fields
        "session_status": session_status.get("status", "idle"),
        "occupancy": shared_state.occupancy_count,
        "present_count": present_count,
        "late_count": late_count,
        "absent_count": absent_count,
        "iot_status": automation_manager.get_status(),
        "phone_alerts_count": len(shared_state.phone_alerts),
        "recent_activity": shared_state.activity_log[:10]
    }


@app.get("/activity-log")
def activity_log():
    """Get recent activity log entries."""
    return {"logs": shared_state.activity_log[:50]}


# ============================================================
# !! PRESERVED: ROOT HEALTH CHECK !!
# ============================================================

@app.get("/")
def home():
    return {"message": "Smart Classroom Backend Running", "version": "2.0"}