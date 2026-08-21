"""
Behavior Tree leaf nodes. `Action` already distinguished sync vs async
callbacks; `Condition` did not, which is the gap these tests cover.
"""

import pytest

from app.cognitive.bt import Condition, NodeStatus


@pytest.mark.asyncio
async def test_condition_awaits_an_async_callback():
    """M10: `Condition.tick` used to call `self.func(blackboard)` unconditionally.
    For a coroutine function, that produces a coroutine *object* rather than a
    boolean, and a coroutine object is truthy - so an async condition that
    should fail was silently reported as SUCCESS instead of being awaited.
    """

    async def async_check(blackboard):
        return blackboard.get("flag", False)

    node = Condition("has_flag", async_check)

    assert await node.tick({"flag": True}) == NodeStatus.SUCCESS
    assert await node.tick({"flag": False}) == NodeStatus.FAILURE


def test_condition_still_supports_a_sync_callback():
    """Sanity check that the coroutine-detection branch didn't regress the
    ordinary synchronous condition path."""

    def sync_check(blackboard):
        return blackboard.get("flag", False)

    node = Condition("has_flag", sync_check)

    import asyncio

    assert asyncio.run(node.tick({"flag": True})) == NodeStatus.SUCCESS
    assert asyncio.run(node.tick({"flag": False})) == NodeStatus.FAILURE
