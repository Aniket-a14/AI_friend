"""Per-client fixed-window rate limiting (H3).

`/token` mints a LiveKit room-join token. `require_session_auth` already
gates *who* can call it, but a valid key (or a loopback caller, which needs
no key at all) doesn't imply unlimited token minting -- a client stuck in a
retry loop, or a deliberately abusive one, can still flood LiveKit session
capacity and this process's own resources.

A single in-memory counter per client IP is deliberately not a distributed
rate limiter: this backend runs as one process for a personal/family
deployment (see `require_session_auth`'s docstring in `main.py`), so there is
no second worker for counts to desync across.
"""

import time
from collections import defaultdict


class FixedWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, tuple[float, int]] = defaultdict(
            lambda: (0.0, 0)
        )

    def allow(self, key: str) -> bool:
        """Returns True and records the call if `key` is under its limit for
        the current window, False (without recording) if it is not."""
        now = time.monotonic()
        window_start, count = self._windows[key]
        if now - window_start >= self.window_seconds:
            self._windows[key] = (now, 1)
            return True
        if count >= self.max_requests:
            return False
        self._windows[key] = (window_start, count + 1)
        return True
