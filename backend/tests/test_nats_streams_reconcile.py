"""P4-11b -- verify-and-retry reconciliation for concurrent stream updates.

JetStream's STREAM.UPDATE has no compare-and-set, so up to six agent
processes (plus the bootstrap script) reconciling the same stream's subjects
at startup can race: one caller's read-modify-write silently overwrites
another's, dropping whichever subject the loser's stale snapshot never saw.
`reconcile_existing_stream` handles this with a verify-then-retry loop
instead of pretending the write is atomic. These tests use a stream name
absent from STREAM_POLICIES so `_apply_policy_to_existing` is a no-op and
only the subjects half is exercised.
"""

import pytest

from app.nats_streams import reconcile_existing_stream

_UNPOLICED_STREAM = "TEST_UNPOLICED_STREAM_NOT_IN_POLICIES"


class _FakeConfig:
    def __init__(self, subjects):
        self.subjects = list(subjects)


class _FakeInfo:
    def __init__(self, subjects):
        self.config = _FakeConfig(subjects)


class FakeJSM:
    """A minimal JetStreamManager stand-in whose `subjects` is the
    server-side ground truth. `race_after_write` subjects are injected as
    the "true" state immediately after each `update_stream` call -- the
    write itself is what happens; `race_after_write` simulates a concurrent
    writer's update landing right after, before this caller's verify-read.
    """

    def __init__(self, initial_subjects, race_after_write=None, race_forever=False):
        self.subjects = set(initial_subjects)
        self.stream_info_calls = 0
        self.update_calls = 0
        self._race_after_write = (
            set(race_after_write) if race_after_write is not None else None
        )
        self._race_forever = race_forever

    async def stream_info(self, name):
        self.stream_info_calls += 1
        return _FakeInfo(self.subjects)

    async def update_stream(self, config):
        self.update_calls += 1
        self.subjects = set(config.subjects)
        if self._race_after_write is not None and (
            self._race_forever or self.update_calls == 1
        ):
            # A concurrent writer's update lands right after ours, before we
            # get to verify -- so what we wrote does not survive.
            self.subjects = set(self._race_after_write)


@pytest.mark.asyncio
async def test_noop_when_already_synchronized():
    """If the desired subject is already present, nothing should be written
    at all -- not even a redundant update_stream call."""
    jsm = FakeJSM(initial_subjects={"a", "b"})

    changed = await reconcile_existing_stream(jsm, _UNPOLICED_STREAM, ["a"])

    assert changed is False
    assert jsm.update_calls == 0


@pytest.mark.asyncio
async def test_recovers_from_a_single_lost_race():
    """A concurrent writer clobbers our first update (dropping our subject
    entirely), but the desired subject must still be present after the
    function returns -- the retry has to converge, not just log and give up.
    """
    jsm = FakeJSM(initial_subjects={"x"}, race_after_write={"y"})

    changed = await reconcile_existing_stream(
        jsm, _UNPOLICED_STREAM, ["a"], max_retries=3
    )

    assert changed is True
    assert "a" in jsm.subjects, (
        "after recovering from a lost race, the caller's desired subject "
        "must actually be present in the final server state"
    )
    assert jsm.update_calls >= 2, "a lost race must trigger at least one retry"


@pytest.mark.asyncio
async def test_gives_up_and_reports_false_after_max_retries_exhausted():
    """If every single attempt keeps losing the race (a pathological but
    possible case), the function must not loop forever or claim success --
    it returns False once max_retries is exhausted."""
    jsm = FakeJSM(initial_subjects={"z"}, race_after_write={"z"}, race_forever=True)

    changed = await reconcile_existing_stream(
        jsm, _UNPOLICED_STREAM, ["a"], max_retries=3
    )

    assert changed is False
    assert jsm.update_calls == 3, "must attempt exactly max_retries times, not loop"
