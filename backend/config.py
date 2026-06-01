import os
from dotenv import load_dotenv

# Load .env file (falls back gracefully if not found)
load_dotenv()

# ============================================================
# HARDWARE COMMUNICATION SETTINGS
# !! DO NOT MODIFY THESE UNLESS HARDWARE CONFIG CHANGES !!
# ============================================================

# Raspberry Pi camera stream URL
PI_STREAM_URL = os.getenv("PI_STREAM_URL", "http://192.168.137.140:5000/video_feed")

# ESP32/ESP8266 IP for IoT control
ESP_IP = os.getenv("ESP_IP", "192.168.137.71")

# ============================================================
# SYSTEM SETTINGS
# ============================================================

# Auto-off delay in seconds (IoT automation)
AUTO_OFF_DELAY = int(os.getenv("AUTO_OFF_DELAY", 30))

# Camera target FPS
CAMERA_FPS = int(os.getenv("CAMERA_FPS", 30))

# ============================================================
# DATABASE SETTINGS
# ============================================================

# MongoDB connection URI
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

# MongoDB database name
MONGO_DB = os.getenv("MONGO_DB", "smart_classroom")

# ============================================================
# SYSTEM CONFIGURATION (configurable via .env)
# ============================================================

# Batch/Division options shown in registration dropdown
# Comma-separated: e.g. "1,2,3,A,B"  or  "SE,TE,BE"
BATCH_OPTIONS_RAW = os.getenv("BATCH_OPTIONS", "1,2,3,A,B")
BATCH_OPTIONS = [b.strip() for b in BATCH_OPTIONS_RAW.split(",") if b.strip()]

# Base cosine similarity threshold for face recognition
# Range: 0.30 (lenient) – 0.70 (strict). Default 0.45 (tuned for InsightFace ArcFace)
FACE_RECOGNITION_THRESHOLD = float(os.getenv("FACE_RECOGNITION_THRESHOLD", "0.45"))

# Attention score weights (must sum to 1.0)
ATTENTION_WEIGHT_POSE       = float(os.getenv("ATTENTION_WEIGHT_POSE",       "0.50"))
ATTENTION_WEIGHT_VISIBILITY = float(os.getenv("ATTENTION_WEIGHT_VISIBILITY", "0.20"))
ATTENTION_WEIGHT_PHONE      = float(os.getenv("ATTENTION_WEIGHT_PHONE",      "0.30"))