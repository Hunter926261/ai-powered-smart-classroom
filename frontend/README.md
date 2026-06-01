# Smart Classroom AI System

## Overview

Smart Classroom AI System is an intelligent classroom automation and attendance management platform that leverages Computer Vision, Artificial Intelligence, Face Recognition, Real-Time Analytics, and IoT automation to create a modern smart classroom environment.

The system automatically detects and recognizes students, marks attendance, manages classroom sessions, provides analytics, and controls classroom devices such as lights and fans through an integrated IoT module.

---

## Key Features

### AI-Based Attendance System

* Real-time face detection and recognition
* Automatic attendance marking
* Present, Late, and Absent classification
* Attendance history tracking
* Duplicate attendance prevention

### Smart Classroom Monitoring

* Live camera feed monitoring
* Multi-person detection
* Face tracking
* Entry and exit logging

### Session Management

* Start and stop classroom sessions
* Session-wise attendance reports
* Automatic attendance status generation
* Historical session records

### IoT Automation

* Smart light control
* Smart fan control
* Automatic and manual operation modes
* Real-time device status monitoring

### Analytics Dashboard

* Total student count
* Attendance statistics
* Present, Late, and Absent analytics
* Real-time classroom monitoring
* Session summaries

### Database Management

* SQLite database support
* MongoDB integration
* Attendance records storage
* Student profile management
* Session history management

---

## System Architecture

```text
Camera Stream
      │
      ▼
YOLOv8 Person Detection
      │
      ▼
InsightFace Recognition
      │
      ▼
Attendance Manager
      │
      ├────────► SQLite Database
      │
      ├────────► MongoDB
      │
      ├────────► Dashboard Analytics
      │
      └────────► IoT Controller
```

---

## Technology Stack

### Backend

* Python 3.10
* FastAPI
* WebSockets
* SQLAlchemy
* SQLite
* MongoDB

### Frontend

* React.js
* Vite
* JavaScript
* CSS

### Artificial Intelligence

* YOLOv8
* InsightFace
* ONNX Runtime GPU
* Deep SORT Tracking

### Computer Vision

* OpenCV
* NumPy

### IoT

* ESP32
* HTTP Communication
* Smart Device Control

### GPU Acceleration

* NVIDIA CUDA
* PyTorch CUDA
* ONNX Runtime GPU

---

## Project Structure

```text
smart-classroom/
│
├── backend/
│   ├── api/
│   ├── core/
│   ├── database/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── websocket/
│   ├── main.py
│   ├── async_detection.py
│   ├── attendance_manager.py
│   ├── face_manager.py
│   ├── session_manager.py
│   └── yolov8n.pt
│
├── frontend/
│   ├── src/
│   ├── public/
│   └── package.json
│
└── README.md
```

---

## AI Models Used

### YOLOv8

Used for:

* Person Detection
* Classroom Occupancy Monitoring
* Real-time Object Detection

### InsightFace

Used for:

* Face Detection
* Face Embedding Generation
* Face Recognition
* Student Identification

### Deep SORT

Used for:

* Multi-person Tracking
* Entry/Exit Tracking
* Identity Persistence

---

## Database Design

### SQLite

Stores:

* Attendance Records
* Student Information
* Session Data

### MongoDB

Stores:

* Analytics Data
* IoT Logs
* Session History
* Real-time Monitoring Data

---

## Installation

### Clone Repository

```bash
git clone https://github.com/your-username/smart-classroom.git
cd smart-classroom
```

### Backend Setup

```bash
cd backend

python -m venv venv

venv\Scripts\activate

pip install -r requirements-lock.txt
```

### Frontend Setup

```bash
cd frontend

npm install

npm run dev
```

---

## Running the Application

### Step 1: Start Camera Stream on Raspberry Pi

Connect the Raspberry Pi camera and navigate to the camera streaming project directory.

```bash
cd ~/Desktop/smart_classroom_pi
```

Start the camera streaming server:

```bash
python camera_stream.py
```

Expected output:

```text
Running on http://0.0.0.0:5000
Running on http://<RASPBERRY_PI_IP>:5000
```

Example:

```text
http://192.168.137.140:5000
```

Verify the stream by opening the URL in a browser:

```text
http://<RASPBERRY_PI_IP>:5000
```

---

### Step 2: Configure Backend Camera URL

Open the backend `.env` file and set:

```env
PI_STREAM_URL=http://<RASPBERRY_PI_IP>:5000/video_feed
```

Example:

```env
PI_STREAM_URL=http://192.168.137.140:5000/video_feed
```

---

### Step 3: Start Backend Server

Navigate to the backend directory:

```bash
cd backend
```

Activate the virtual environment:

```bash
venv\Scripts\activate
```

Start the FastAPI server:

```bash
uvicorn main:app
```

Expected output:

```text
MongoDB Connected
InsightFace GPU Enabled
YOLO GPU Enabled
Application startup complete
```

Backend URL:

```text
http://127.0.0.1:8000
```

API Documentation:

```text
http://127.0.0.1:8000/docs
```

---

### Step 4: Start Frontend

Navigate to the frontend directory:

```bash
cd frontend
```

Install dependencies (first time only):

```bash
npm install
```

Run the frontend:

```bash
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

---

### Step 5: Verify System Operation

1. Open the Dashboard.
2. Verify Camera Status is Online.
3. Register a student face.
4. Start a classroom session.
5. Stand in front of the camera.
6. Verify:

   * Face detection works.
   * Student name appears.
   * Attendance is marked automatically.
   * Dashboard statistics update in real time.
   * IoT controls respond correctly.

---

### Deployment Sequence

```text
Raspberry Pi Camera Stream
           │
           ▼
      Flask Server
           │
           ▼
       FastAPI Backend
           │
           ▼
 YOLOv8 + InsightFace
           │
           ▼
 SQLite + MongoDB
           │
           ▼
      React Dashboard
```

---

## Dashboard Modules

### Dashboard

Displays:

* Total Students
* Present Students
* Active Camera Status
* Attendance Statistics

### Student Registration

Allows:

* Student Registration
* Face Enrollment
* Student Database Management

### Attendance

Provides:

* Live Camera Feed
* Real-Time Recognition
* Attendance Tracking

### Attention Analytics

Provides:

* Attendance Insights
* Classroom Activity Monitoring

### IoT Control

Controls:

* Lights
* Fans
* Smart Classroom Devices

### History

Displays:

* Attendance History
* Session Reports
* Historical Analytics

---

## Performance Optimizations

* GPU Accelerated Face Recognition
* GPU Accelerated Object Detection
* Async Detection Pipeline
* Frame Skipping Optimization
* Real-Time WebSocket Updates
* Multi-threaded Processing

---

## Future Enhancements

* Emotion Detection
* Student Attention Monitoring
* Mobile Application
* Cloud Deployment
* Voice Assistant Integration
* SMS/Email Notifications
* Multi-Camera Support
* AI-Based Classroom Insights

---

## Applications

* Schools
* Colleges
* Universities
* Coaching Institutes
* Corporate Training Centers

---

