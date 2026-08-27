"""
A small durable queue for proactive outreach that had nowhere to go.

Phase 3.1: `subconscious_agent` generates a proactive "thought" on a system
tick when the agent is eligible to reach out. If nobody is connected to the
LiveKit room right then, publishing it to `chat.input` as usual would trigger
a full cognitive turn, TTS, and audio synthesis that `transport_agent` has
nowhere to play -- wasted work whose only trace was a log line, and the
thought itself was simply gone.

Queuing the raw thought text here instead means it costs nothing until
someone reconnects, at which point it is replayed through the exact same
`chat.input` -> ... -> `chat.output` pipeline a live proactive thought already
uses -- not a parallel delivery path (e.g. synthesizing stored audio through
`transport_agent` directly) that would have to be kept correct twice, and
would need its own understanding of `voice-agent`'s Rust-side `ChatOutput`
consumption to get right.

Deliberately its own tiny SQLite table rather than a new `StateService`
concern: this is a queue (ordered, consumed once, batch-drained), not affect
state (a single current value overwritten in place), and conflating shapes
like that is exactly how `validate_response` and `_validate_partial_response`
drifted apart (see Phase 3.2). Shares `StateService`'s own `db_path` (a
different table in the same file) rather than a new one, since it is exactly
as durable as the state it is meant to survive a restart alongside.
"""

import logging
import sqlite3
import time

logger = logging.getLogger(__name__)

# Once past this, the oldest thoughts are dropped rather than accumulating
# forever across a very long absence -- replaying a dozen stale thoughts on
# reconnect would read as confused, not attentive.
MAX_PENDING = 5


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS proactive_outreach_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thought TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    return conn


def enqueue(db_path: str, thought: str) -> None:
    """Store a proactive thought that had no one to reach.

    Trims to `MAX_PENDING`, oldest first. Never raises: a queue write that
    fails should lose one thought, not take down the tick that produced it.
    """
    try:
        conn = _connect(db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO proactive_outreach_queue (thought, created_at) "
                    "VALUES (?, ?)",
                    (thought, time.time()),
                )
                conn.execute(
                    """
                    DELETE FROM proactive_outreach_queue WHERE id NOT IN (
                        SELECT id FROM proactive_outreach_queue
                        ORDER BY created_at DESC LIMIT ?
                    )
                    """,
                    (MAX_PENDING,),
                )
        finally:
            conn.close()
    except Exception:
        logger.exception("[ProactiveQueue] Could not enqueue a pending thought.")


def pop_all(db_path: str) -> list[str]:
    """Return every pending thought, oldest first, and clear the queue.

    Popped as one batch rather than drained one at a time: a reconnect
    handler wants "what did I miss," not a queue it has to keep polling.
    Never raises: a read failure should surface as "nothing pending," not
    crash whatever just reconnected.
    """
    try:
        conn = _connect(db_path)
        try:
            with conn:
                cursor = conn.execute(
                    "SELECT thought FROM proactive_outreach_queue ORDER BY created_at ASC"
                )
                thoughts = [row[0] for row in cursor.fetchall()]
                conn.execute("DELETE FROM proactive_outreach_queue")
            return thoughts
        finally:
            conn.close()
    except Exception:
        logger.exception("[ProactiveQueue] Could not read the pending queue.")
        return []
