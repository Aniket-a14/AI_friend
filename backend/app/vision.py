import mss
import numpy as np
import cv2
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ScreenLink:
    """High-performance primary monitor capture."""

    def __init__(self):
        try:
            self.sct = mss.mss()
            try:
                self.monitor = self.sct.monitors[1]
            except IndexError:
                self.monitor = self.sct.monitors[0]
            self.headless = False
        except Exception as e:
            logger.warning(f"[Vision] Running in headless mode (No Display): {e}")
            self.sct = None
            self.monitor = None
            self.headless = True

    def _compress_frame(self, frame: np.ndarray) -> Optional[bytes]:
        if frame is None:
            return None
        height, width = frame.shape[:2]
        target_width = 512
        if width > target_width:
            scale = target_width / width
            new_height = int(height * scale)
            frame = cv2.resize(frame, (target_width, new_height))

        # 50% Quality JPEG for low-latency transport
        _, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        return buffer.tobytes()

    def capture_frame(self) -> Optional[bytes]:
        """Captures and returns a compressed JPEG frame of the screen."""
        if self.headless:
            return None

        try:
            sct_img = self.sct.grab(self.monitor)
            img = np.array(sct_img)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return self._compress_frame(img)
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return None


class CameraLink:
    """Local camera capture for visual grounding."""

    def __init__(self):
        self.cap = None

    def _compress_frame(self, frame: np.ndarray) -> Optional[bytes]:
        if frame is None:
            return None
        height, width = frame.shape[:2]
        target_width = 512
        if width > target_width:
            scale = target_width / width
            new_height = int(height * scale)
            frame = cv2.resize(frame, (target_width, new_height))

        # 50% Quality JPEG for low-latency transport
        _, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        return buffer.tobytes()

    def _ensure_cap(self):
        if self.cap is None or not self.cap.isOpened():
            self.cap = cv2.VideoCapture(0)

    def capture_frame(self) -> Optional[bytes]:
        """Captures and returns a compressed JPEG frame from the camera."""
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
        """Release camera resources."""
        if self.cap:
            self.cap.release()
            self.cap = None
