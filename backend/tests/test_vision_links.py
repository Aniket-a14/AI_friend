import contextlib
import importlib
import sys

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
