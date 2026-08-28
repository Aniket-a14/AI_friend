# Deferred annotation evaluation (H4): `frame: np.ndarray` below is only ever
# used as a type hint, but without this, Python evaluates it at class-body
# execution time - so a missing numpy install would raise AttributeError on
# `np.ndarray` even after guarding the import itself.
from __future__ import annotations

try:
    import mss
except ImportError:
    mss = None

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]  # optional dependency; guarded at every call site

try:
    import cv2
except ImportError:
    cv2 = None

import logging

logger = logging.getLogger(__name__)


class ScreenLink:
    """High-performance primary monitor capture."""

    def __init__(self):
        if mss is None or np is None:
            missing = "mss" if mss is None else "numpy"
            logger.warning(
                f"[Vision] {missing} dependency is missing. Running in headless mode."
            )
            self.sct = None
            self.monitor = None
            self.headless = True
            return

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

    def _compress_frame(self, frame: np.ndarray) -> bytes | None:
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

    def _ensure_sct(self):
        """Retry display discovery if currently headless (#169).

        Unlike `CameraLink._ensure_cap`, which already retried
        `cv2.VideoCapture(0)` on every call, `ScreenLink` decided `headless`
        once at construction and never looked again - a display attached
        after startup (or a headless container later given one) left the
        agent blind for the rest of the process's life.
        """
        if not self.headless or mss is None or np is None:
            return
        try:
            self.sct = mss.mss()
            try:
                self.monitor = self.sct.monitors[1]
            except IndexError:
                self.monitor = self.sct.monitors[0]
            self.headless = False
            logger.info("[Vision] Screen capture recovered; a display is available.")
        except Exception:
            pass  # nosec B110 - still headless; capture_frame() below returns None as before

    def capture_frame(self) -> bytes | None:
        """Captures and returns a compressed JPEG frame of the screen."""
        self._ensure_sct()
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

    def close(self):
        """Release the mss display connection (P3-4).

        Unlike `CameraLink.close()`, which existed already, nothing ever
        released `self.sct` -- `mss.mss()` holds an X11/display connection
        that outlives the process otherwise.
        """
        if self.sct:
            try:
                self.sct.close()
            except Exception as e:
                logger.debug("[Vision] Error closing screen capture: %s", e)
            self.sct = None


class CameraLink:
    """Local camera capture for visual grounding."""

    def __init__(self):
        self.cap = None
        if cv2 is None:
            logger.warning(
                "[Vision] cv2 dependency is missing. Camera capture disabled."
            )

    def _compress_frame(self, frame: np.ndarray) -> bytes | None:
        if frame is None or cv2 is None:
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
        if cv2 is None:
            raise RuntimeError("cv2 dependency is missing. Camera capture unavailable.")
        if self.cap is None or not self.cap.isOpened():
            # Release the stale handle before replacing it (M3) - re-assigning
            # `self.cap` without this leaks the underlying /dev/video0 device
            # handle every time isOpened() comes back False on a live device.
            if self.cap is not None:
                self.cap.release()
            self.cap = cv2.VideoCapture(0)

    def capture_frame(self) -> bytes | None:
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
