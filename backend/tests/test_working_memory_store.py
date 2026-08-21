import asyncio
import threading

from app.state.working_memory_store import WorkingMemoryStore


def _make_store(db_path: str) -> WorkingMemoryStore:
    """A store with no reachable Redis, forced onto the SQLite fallback."""
    return WorkingMemoryStore(
        redis_host="127.0.0.1",
        redis_port=1,  # nothing listens here; connect fails fast
        db_path=db_path,
        max_turns=8,
    )


def test_add_turn_and_get_recent_turns_do_not_block_the_event_loop(tmp_path):
    """`add_turn`/`get_recent_turns` must run their blocking I/O off the loop.

    Regression for C7: these were plain `def` methods doing blocking sqlite3
    (and, with Redis reachable, blocking `redis.Redis`) calls. Called directly
    from async code (as scripts/research/estimate_realtime_latency.py does),
    they stalled the event loop for the duration of the I/O. A concurrently
    scheduled task should keep making progress while add_turn runs.
    """
    store = _make_store(str(tmp_path / "working.db"))
    progress = []

    async def ticker():
        for i in range(20):
            progress.append(i)
            await asyncio.sleep(0.001)

    async def run():
        ticker_task = asyncio.create_task(ticker())
        await store.add_turn(role="user", content="hello", metadata={"i": 0})
        await asyncio.sleep(0)  # let the ticker get scheduled at least once
        await ticker_task
        return await store.get_recent_turns(limit=8)

    turns = asyncio.run(run())

    assert len(progress) == 20
    assert len(turns) == 1
    assert turns[0]["content"] == "hello"


def test_add_turn_runs_off_the_calling_thread(tmp_path):
    """The blocking work must happen in a worker thread, not inline on the
    caller's thread - otherwise wrapping it in `async def` is theater."""
    store = _make_store(str(tmp_path / "working.db"))
    caller_thread = threading.current_thread()
    seen_threads = []

    original = store._sync_add_turn

    def spy(*args, **kwargs):
        seen_threads.append(threading.current_thread())
        return original(*args, **kwargs)

    store._sync_add_turn = spy

    asyncio.run(store.add_turn(role="user", content="hi"))

    assert len(seen_threads) == 1
    assert seen_threads[0] is not caller_thread


def test_state_var_roundtrip_via_sqlite_fallback(tmp_path):
    store = _make_store(str(tmp_path / "working.db"))

    async def run():
        await store.set_state_var("mood", {"valence": 0.4})
        return await store.get_state_var("mood")

    result = asyncio.run(run())
    assert result == {"valence": 0.4}


def test_clear_turns_empties_the_store(tmp_path):
    store = _make_store(str(tmp_path / "working.db"))

    async def run():
        await store.add_turn(role="user", content="hi")
        await store.clear_turns()
        return await store.get_recent_turns()

    turns = asyncio.run(run())
    assert turns == []
