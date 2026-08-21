"""
#153: worker agent processes run via plain `asyncio.run(main())`, not under
a framework like uvicorn (which installs its own signal handling for free
for main.py's FastAPI server). Python's default disposition for SIGTERM is
to kill the process outright - no exception is raised, so no graceful
`stop()` (NATS unsubscribe, GraphDB close, task cancellation) ever ran.
`install_shutdown_signal_handlers` closes that gap by wiring both SIGTERM
and SIGINT to the same shutdown-event path.
"""

import asyncio
import os
import signal

import pytest

from app.agents.base import install_shutdown_signal_handlers


@pytest.mark.asyncio
async def test_sigterm_sets_the_shutdown_event():
    """A real SIGTERM sent to this process must reach the event - not just
    SIGINT, which Python already translates to KeyboardInterrupt by default.
    """
    shutdown_event = asyncio.Event()
    install_shutdown_signal_handlers(shutdown_event)

    os.kill(os.getpid(), signal.SIGTERM)
    await asyncio.wait_for(shutdown_event.wait(), timeout=2.0)

    assert shutdown_event.is_set()


@pytest.mark.asyncio
async def test_sigint_still_sets_the_shutdown_event():
    """SIGINT must keep working through the same unified path."""
    shutdown_event = asyncio.Event()
    install_shutdown_signal_handlers(shutdown_event)

    os.kill(os.getpid(), signal.SIGINT)
    await asyncio.wait_for(shutdown_event.wait(), timeout=2.0)

    assert shutdown_event.is_set()


@pytest.mark.asyncio
async def test_without_a_handler_the_event_never_sets_on_its_own():
    """Sanity check for the test technique itself: the event must not be
    set just by existing - only the signal handler should set it."""
    shutdown_event = asyncio.Event()
    await asyncio.sleep(0.05)
    assert not shutdown_event.is_set()
