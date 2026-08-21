"""
NATS reconnect backoff. `BaseAgent.connect` used a static `reconnect_time_wait`,
so every agent process in the mesh (brain, system, subconscious, surfacing,
transport) retried at the exact same fixed interval - a NATS restart makes
them all hammer it in lockstep on every attempt. `_reconnect_delay_with_backoff`
is the `reconnect_to_server_handler` callback that replaces it.
"""

from types import SimpleNamespace

from app.agents.base import (
    _RECONNECT_MAX_DELAY_SECONDS,
    _reconnect_delay_with_backoff,
)


def _server(reconnects: int):
    return SimpleNamespace(reconnects=reconnects)


def test_delay_grows_with_attempt_count():
    """M6: successive attempts must wait longer, not the same fixed interval
    every time. Jitter is bounded to [0, 1) and the base doubles each attempt
    (1.0, 2.0, 4.0...), so the value ranges for consecutive attempts
    ([1.0, 2.0), [2.0, 3.0), [4.0, 5.0)) never overlap - ordering is
    deterministic even with random jitter in play.
    """
    _, delay0 = _reconnect_delay_with_backoff([_server(0)], {})
    _, delay1 = _reconnect_delay_with_backoff([_server(1)], {})
    _, delay2 = _reconnect_delay_with_backoff([_server(2)], {})

    assert delay0 < delay1 < delay2


def test_delay_is_capped_at_the_maximum():
    """A long outage must not make the wait grow forever."""
    _, delay = _reconnect_delay_with_backoff([_server(50)], {})
    assert delay <= _RECONNECT_MAX_DELAY_SECONDS + 1.0  # +1 for jitter headroom


def test_delay_includes_jitter_so_concurrent_agents_do_not_align():
    """Multiple calls at the same attempt count must not produce identical
    delays - that's the whole point of adding jitter (thundering herd)."""
    delays = {_reconnect_delay_with_backoff([_server(3)], {})[1] for _ in range(20)}
    assert len(delays) > 1


def test_selected_server_is_left_to_the_client_default():
    """There is only ever one configured NATS server; this handler should
    only take over delay computation, not server selection."""
    selected, _ = _reconnect_delay_with_backoff([_server(0)], {})
    assert selected is None


def test_no_eligible_servers_does_not_raise():
    selected, delay = _reconnect_delay_with_backoff([], {})
    assert selected is None
    assert delay >= 0
