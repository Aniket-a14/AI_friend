import contextlib
import importlib
import sys
from unittest.mock import MagicMock, patch

import app.vision.links as links_module


@contextlib.contextmanager
def _numpy_uninstalled():
    """Simulate numpy not being installed, reload `app.vision.links` under
    that condition, and restore the real module before yielding control back.

    `sys.modules["numpy"] = None` is the standard way to force `import numpy`
    to raise ImportError without needing to intercept `builtins.__import__`.
    """
    real_numpy = sys.modules.get("numpy")
    sys.modules["numpy"] = None
    try:
        importlib.reload(links_module)
        yield links_module
    finally:
        if real_numpy is not None:
            sys.modules["numpy"] = real_numpy
        else:
            sys.modules.pop("numpy", None)
        importlib.reload(links_module)


def test_module_import_survives_missing_numpy():
    """H4 regression: `import numpy as np` was unguarded (unlike mss/cv2 in
    the same file), so a headless/minimal install without numpy couldn't
    even import this module, crashing vision startup entirely.
    """
    with _numpy_uninstalled() as reloaded:
        assert reloaded.np is None


def test_screen_link_goes_headless_without_numpy():
    with _numpy_uninstalled() as reloaded:
        link = reloaded.ScreenLink()
        assert link.headless is True
        assert link.capture_frame() is None


def test_screen_link_still_works_normally_with_numpy_present():
    # Sanity check that the guard didn't regress the ordinary import path.
    assert links_module.np is not None


def test_screen_link_retries_display_discovery_after_going_headless():
    """#169: once `headless=True`, ScreenLink used to never look for a
    display again - a display attached after startup (or a headless
    container later given one) left the agent blind for the process's
    entire remaining life, unlike CameraLink, which already retried
    `cv2.VideoCapture(0)` on every call.
    """
    with patch.object(links_module, "mss", MagicMock()) as mock_mss:
        mock_mss.mss.side_effect = Exception("no display yet")

        link = links_module.ScreenLink()
        assert link.headless is True
        assert link.capture_frame() is None

        # Display becomes available; the next capture attempt (via the same
        # public entry point the capture loop calls every tick) should
        # recover without needing the agent to be restarted.
        recovered_sct = MagicMock()
        recovered_sct.monitors = [{}, {"width": 1920, "height": 1080}]
        recovered_sct.grab.return_value = MagicMock()
        mock_mss.mss.side_effect = None
        mock_mss.mss.return_value = recovered_sct

        with patch.object(links_module, "np") as mock_np, patch.object(
            links_module, "cv2"
        ) as mock_cv2:
            mock_np.array.return_value = mock_np.array.return_value
            mock_cv2.cvtColor.return_value = mock_cv2.cvtColor.return_value
            mock_cv2.imencode.return_value = (True, MagicMock(tobytes=lambda: b"jpg"))
            link.capture_frame()

        assert link.headless is False
        assert link.sct is recovered_sct


def test_camera_link_releases_stale_handle_before_reopening():
    """M3: `_ensure_cap` used to reassign `self.cap` to a fresh
    `VideoCapture` whenever the existing one reported `isOpened() is False`,
    without releasing it first - leaking the underlying /dev/video0 handle on
    every such recovery instead of just the first open.
    """
    with patch.object(links_module, "cv2", MagicMock()) as mock_cv2:
        stale_cap = MagicMock()
        stale_cap.isOpened.return_value = False
        fresh_cap = MagicMock()
        mock_cv2.VideoCapture.return_value = fresh_cap

        link = links_module.CameraLink()
        link.cap = stale_cap

        link._ensure_cap()

        stale_cap.release.assert_called_once()
        assert link.cap is fresh_cap
