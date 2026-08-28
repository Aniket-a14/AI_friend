"""
`app/state/proactive_queue.py` -- the durable holding pen for a proactive
thought that had nobody to reach.
"""

from app.state import proactive_queue


def test_pop_all_returns_nothing_from_an_empty_queue(tmp_path):
    db_path = str(tmp_path / "state.db")
    assert proactive_queue.pop_all(db_path) == []


def test_enqueue_then_pop_all_round_trips_a_single_thought(tmp_path):
    db_path = str(tmp_path / "state.db")
    proactive_queue.enqueue(db_path, "I wonder how their project is going.")
    assert proactive_queue.pop_all(db_path) == [
        "I wonder how their project is going."
    ]


def test_pop_all_returns_thoughts_oldest_first(tmp_path):
    db_path = str(tmp_path / "state.db")
    proactive_queue.enqueue(db_path, "first")
    proactive_queue.enqueue(db_path, "second")
    proactive_queue.enqueue(db_path, "third")
    assert proactive_queue.pop_all(db_path) == ["first", "second", "third"]


def test_pop_all_drains_the_queue(tmp_path):
    """A second pop after the first must find nothing left -- otherwise a
    thought would be replayed twice on two separate reconnects."""
    db_path = str(tmp_path / "state.db")
    proactive_queue.enqueue(db_path, "only thought")
    proactive_queue.pop_all(db_path)
    assert proactive_queue.pop_all(db_path) == []


def test_more_than_max_pending_keeps_only_the_newest(tmp_path):
    db_path = str(tmp_path / "state.db")
    for i in range(proactive_queue.MAX_PENDING + 3):
        proactive_queue.enqueue(db_path, f"thought-{i}")

    remaining = proactive_queue.pop_all(db_path)

    assert len(remaining) == proactive_queue.MAX_PENDING
    # The oldest ones (thought-0, thought-1, thought-2) must be the ones
    # dropped, not an arbitrary subset -- a friend catching up should hear
    # its most recent thinking, not whatever happened to survive.
    assert remaining[0] == "thought-3"
    assert remaining[-1] == f"thought-{proactive_queue.MAX_PENDING + 2}"


def test_queue_survives_a_fresh_connection_to_the_same_file(tmp_path):
    """Simulates a process restart: enqueue, then read back via a totally
    separate call (a fresh sqlite3.connect happens inside each function)."""
    db_path = str(tmp_path / "state.db")
    proactive_queue.enqueue(db_path, "still here after a restart")
    assert proactive_queue.pop_all(db_path) == ["still here after a restart"]
