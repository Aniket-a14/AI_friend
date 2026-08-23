from unittest.mock import patch

from app.rate_limit import FixedWindowRateLimiter


def test_allows_up_to_the_limit_then_blocks():
    limiter = FixedWindowRateLimiter(max_requests=3, window_seconds=60.0)
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is False


def test_keys_are_independent():
    limiter = FixedWindowRateLimiter(max_requests=1, window_seconds=60.0)
    assert limiter.allow("client-a") is True
    assert limiter.allow("client-b") is True
    assert limiter.allow("client-a") is False
    assert limiter.allow("client-b") is False


def test_window_resets_after_it_elapses():
    limiter = FixedWindowRateLimiter(max_requests=1, window_seconds=10.0)
    with patch("time.monotonic", return_value=1000.0):
        assert limiter.allow("client") is True
        assert limiter.allow("client") is False
    with patch("time.monotonic", return_value=1011.0):
        assert limiter.allow("client") is True


def test_stale_windows_are_swept_so_the_dict_does_not_grow_forever():
    """P3-7: one entry per distinct client IP was kept forever -- a client
    that calls once and never again occupied a slot for the process's whole
    life. A stale (window already elapsed) entry must be dropped once the
    sweep interval is reached, not accumulate indefinitely."""
    limiter = FixedWindowRateLimiter(max_requests=5, window_seconds=10.0)
    limiter._sweep_every = 5

    with patch("time.monotonic", return_value=1000.0):
        for i in range(4):
            limiter.allow(f"client-{i}")
    assert len(limiter._windows) == 4

    # All 4 windows are now stale. This 5th call since the last reset must
    # trigger a sweep and drop them, leaving only the key it just wrote.
    with patch("time.monotonic", return_value=1050.0):
        limiter.allow("client-new")

    assert list(limiter._windows.keys()) == ["client-new"]
