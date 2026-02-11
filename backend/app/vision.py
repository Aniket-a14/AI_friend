import mss
import numpy as np
import cv2
import asyncio
import logging

logger = logging.getLogger(__name__)

class ScreenLink:
    def __init__(self):
        self.sct = mss.mss()
        try:
            self.monitor = self.sct.monitors[1]
        except IndexError:
            self.monitor = self.sct.monitors[0]
            
    def _compress_frame(self, frame):
        if frame is None: return None
        height, width = frame.shape[:2]
        target_width = 512 # Lowered for stability in 2026
        if width > target_width:
            scale = target_width / width
            new_height = int(height * scale)
            frame = cv2.resize(frame, (target_width, new_height))
        
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        return buffer.tobytes()

    def capture_frame(self):
        try:
            sct_img = self.sct.grab(self.monitor)
            img = np.array(sct_img)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return self._compress_frame(img)
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return None

class CameraLink:
    def __init__(self):
        self.cap = None
    
    def _compress_frame(self, frame):
        if frame is None: return None
        height, width = frame.shape[:2]
        target_width = 512
        if width > target_width:
            scale = target_width / width
            new_height = int(height * scale)
            frame = cv2.resize(frame, (target_width, new_height))
            
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        return buffer.tobytes()

    def _ensure_cap(self):
        if self.cap is None or not self.cap.isOpened():
            self.cap = cv2.VideoCapture(0)
            
    def capture_frame(self):
        try:
            self._ensure_cap()
            ret, frame = self.cap.read()
            if not ret:
                return None
            return self._compress_frame(frame)
        except Exception as e:
            logger.error(f"Camera capture failed: {e}")
            return None

    def close(self):
        if self.cap:
            self.cap.release()
            self.cap = None
