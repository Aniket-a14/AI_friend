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
