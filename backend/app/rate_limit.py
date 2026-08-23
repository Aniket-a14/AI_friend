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
        # P3-7: one entry per distinct client IP was kept forever -- a client
        # that calls once and never again still occupies a slot for the life
        # of the process. A lazy sweep every `_sweep_every` calls drops any
        # window whose start is already outside `window_seconds` (a window
        # that old contributes nothing to the current limit either way), so
        # the dict stays bounded to roughly the clients active in the last
        # sweep interval instead of every client ever seen.
        self._calls_since_sweep = 0
        self._sweep_every = 200

    def allow(self, key: str) -> bool:
        """Returns True and records the call if `key` is under its limit for
        the current window, False (without recording) if it is not."""
        now = time.monotonic()
        self._calls_since_sweep += 1
        if self._calls_since_sweep >= self._sweep_every:
            self._sweep(now)

        window_start, count = self._windows[key]
        if now - window_start >= self.window_seconds:
            self._windows[key] = (now, 1)
            return True
        if count >= self.max_requests:
            return False
        self._windows[key] = (window_start, count + 1)
        return True

    def _sweep(self, now: float):
        self._calls_since_sweep = 0
        stale_keys = [
            key
            for key, (window_start, _count) in self._windows.items()
            if now - window_start >= self.window_seconds
        ]
        for key in stale_keys:
            del self._windows[key]
