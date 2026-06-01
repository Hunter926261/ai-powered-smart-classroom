"""
Device Detection Utility — Smart Classroom Manager
====================================================
Centralised GPU/CPU detection used by FaceManager and AsyncDetection.
Returns the correct device string and InsightFace ctx_id so both
modules use the same hardware without hardcoding 'cuda' or 0.

!! HARDWARE: No ESP32 / Raspberry Pi logic here — pure compute !!
"""

import torch


def get_device():
    """
    Auto-detect compute device.

    Returns:
        tuple: (device_str, insightface_ctx_id)
            device_str: "cuda" or "cpu"  (used for YOLO .to(device_str))
            ctx_id:      0 or -1          (used for insightface prepare())
    """
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        print(f"[Device] GPU detected: {name}")
        return "cuda", 0

    print("[Device] No GPU found — running on CPU (slower but functional)")
    return "cpu", -1
