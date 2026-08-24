"""Shared helper for fire-and-forget asyncio tasks (P4-8).

`asyncio.create_task(coro)` with the returned `Task` discarded is a
documented pitfall, not a style nit: the event loop holds only a *weak*
reference to a task once it is scheduled, so nothing stops the garbage
collector from reclaiming -- and silently cancelling, mid-execution, with no
exception raised anywhere -- a `Task` object nothing else refers to. The
`asyncio.create_task` docs call this out directly: *"Important: Save a
reference to the result of this function, to avoid a task disappearing mid
execution."*

Several call sites across the mesh (`conversation_store.log_message`
fire-and-forget writes, `cache.sync` broadcasts, `state.broadcast`, the
per-frame `agent.voice.modulation` publish, background audio processing,
heartbeat loops) created a task and threw the reference away. Each was a
plausible, easy-to-miss instance of the same bug, so this gives every one of
them a single fix rather than a dozen ad hoc `self._foo_task` attributes.
"""

import asyncio


def spawn_background(task_set: "set[asyncio.Task]", coro) -> asyncio.Task:
    """Schedule `coro` and keep a strong reference in `task_set` until it
    finishes, then let it go. `task_set` is owned by the caller (usually one
    `set()` per instance) so unrelated background tasks on different objects
    don't share a retention lifetime."""
    task = asyncio.create_task(coro)
    task_set.add(task)
    task.add_done_callback(task_set.discard)
    return task
