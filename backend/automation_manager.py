"""
Automation Manager — Smart Classroom Manager
=============================================
Controls IoT devices (lights, fans) via ESP32 HTTP commands.

!! HARDWARE CRITICAL !!
  - ESP_IP and command paths are PRESERVED from original
  - Existing /light/on and /light/off commands unchanged
  - Fan commands use /fan/on and /fan/off (to be added to ESP firmware)
"""

import requests
import threading
import time
from datetime import datetime

import shared_state
from config import ESP_IP, AUTO_OFF_DELAY


class AutomationManager:

    def __init__(self):

        # !! PRESERVED: ESP32 IP from config !!
        self.esp_ip = ESP_IP

        # Operating mode: AUTO or MANUAL
        self.mode = "AUTO"

        # Device states
        self.light_on = False
        self.fan_on = False

        # Timer for auto-off
        self.last_seen = time.time()

        # Start auto-loop daemon thread
        thread = threading.Thread(
            target=self.auto_loop,
            daemon=True
        )
        thread.start()

    # ----------------------------------------------------------
    # CORE ESP COMMUNICATION (preserved from original)
    # ----------------------------------------------------------

    def send_command(self, command):
        """
        Send HTTP GET command to ESP32.
        !! DO NOT CHANGE the URL format — matches ESP firmware !!
        """
        try:
            url = f"http://{self.esp_ip}/{command}"
            requests.get(url, timeout=2)
            print(f"[IoT] ESP Command: {command}")
        except Exception as e:
            print(f"[IoT] ESP Error: {e}")

    # ----------------------------------------------------------
    # LIGHT CONTROL (preserved behavior)
    # ----------------------------------------------------------

    def turn_on(self):
        """Turn lights ON via ESP32."""
        if not self.light_on:
            self.send_command("light/on")   # !! PRESERVED command !!
            self.light_on = True
            self._log_action("Lights", "ON")

    def turn_off(self):
        """Turn lights OFF via ESP32."""
        if self.light_on:
            self.send_command("light/off")  # !! PRESERVED command !!
            self.light_on = False
            self._log_action("Lights", "OFF")

    # ----------------------------------------------------------
    # FAN CONTROL (new — maps to /fan/on, /fan/off on ESP firmware)
    # ----------------------------------------------------------

    def turn_fan_on(self):
        """Turn fans ON via ESP32."""
        if not self.fan_on:
            self.send_command("fan/on")
            self.fan_on = True
            self._log_action("Fans", "ON")

    def turn_fan_off(self):
        """Turn fans OFF via ESP32."""
        if self.fan_on:
            self.send_command("fan/off")
            self.fan_on = False
            self._log_action("Fans", "OFF")

    # ----------------------------------------------------------
    # MODE CONTROL (preserved behavior, extended)
    # ----------------------------------------------------------

    def set_mode(self, mode: str):
        """Change automation mode: AUTO or MANUAL."""
        self.mode = mode
        print(f"[IoT] Mode Changed: {mode}")
        self._log_action("System", f"Mode set to {mode}")

    # ----------------------------------------------------------
    # MANUAL CONTROLS (preserved from original)
    # ----------------------------------------------------------

    def manual_on(self):
        """Manual lights ON — switches to MANUAL mode."""
        self.mode = "MANUAL"
        self.turn_on()

    def manual_off(self):
        """Manual lights OFF — switches to MANUAL mode."""
        self.mode = "MANUAL"
        self.turn_off()

    def manual_fan_on(self):
        """Manual fans ON — switches to MANUAL mode."""
        self.mode = "MANUAL"
        self.turn_fan_on()

    def manual_fan_off(self):
        """Manual fans OFF — switches to MANUAL mode."""
        self.mode = "MANUAL"
        self.turn_fan_off()

    # ----------------------------------------------------------
    # AUTO TRIGGER (called by async_detection when person seen)
    # ----------------------------------------------------------

    def person_detected(self):
        """
        Called when at least one person is detected in frame.
        Updates last_seen and turns on devices in AUTO mode.
        !! PRESERVED behavior from original !!
        """
        self.last_seen = time.time()
        if self.mode == "AUTO":
            self.turn_on()
            self.turn_fan_on()

    def no_person_detected(self):
        """Called when classroom is empty in AUTO mode."""
        pass  # Handled by auto_loop timer

    # ----------------------------------------------------------
    # AUTO LOOP (preserved, extended for fans)
    # ----------------------------------------------------------

    def auto_loop(self):
        """
        Background daemon — turns off devices after AUTO_OFF_DELAY
        seconds of no person detection.
        !! PRESERVED behavior from original !!
        """
        while True:
            if self.mode == "AUTO":
                elapsed = time.time() - self.last_seen
                if elapsed > AUTO_OFF_DELAY:
                    self.turn_off()
                    self.turn_fan_off()
            time.sleep(1)

    # ----------------------------------------------------------
    # STATUS API
    # ----------------------------------------------------------

    def get_status(self) -> dict:
        """Return current IoT device state for the frontend."""
        return {
            "mode": self.mode,
            "light_on": self.light_on,
            "fan_on": self.fan_on,
            "esp_ip": self.esp_ip,
            "recent_logs": shared_state.iot_logs[:20]
        }

    # ----------------------------------------------------------
    # HELPER
    # ----------------------------------------------------------

    def _log_action(self, device: str, action: str):
        """Log IoT action to shared_state and MongoDB."""
        timestamp = datetime.now().strftime("%H:%M")
        entry = {
            "timestamp": timestamp,
            "device": device,
            "action": action,
            "mode": self.mode
        }
        shared_state.iot_logs.insert(0, entry)
        # Trim log to 50 entries
        if len(shared_state.iot_logs) > 50:
            shared_state.iot_logs.pop()

        # Also log to MongoDB (non-blocking best-effort)
        try:
            from database.mongo_client import mongo
            mongo.log_iot_action(device, action, self.mode)
        except Exception:
            pass


# Singleton instance
automation_manager = AutomationManager()