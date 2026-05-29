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