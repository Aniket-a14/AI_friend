"""Live text chat + transcript, over the real mesh (roadmap Phase 5.2).

The web UI's only text path onto the cognitive pipeline -- publishes
`chat.input` and streams `chat.output` back, exactly like
`scripts/talk.py`'s REPL, just fanned out over a WebSocket instead of a
terminal loop.

One shared subscription for the process, not one per browser tab:
`BaseAgent.subscribe` always creates a *durable* JetStream consumer (there is
no ephemeral option -- see `BaseAgent.subscribe`'s docstring), so opening a
fresh durable per WebSocket connection would leak one consumer per tab-open
or reconnect, forever. `ChatBridge` holds the single subscription for the
app's lifetime (started/stopped from `main.py`'s lifespan) and fans each
`chat.output` message out to every currently-connected socket in-process via
a per-connection queue instead.

Auth is intentionally not handled here: this router is mounted in `main.py`
alongside the other Phase 5.1 routers, under the same
`dependencies=[Depends(require_session_auth)]` -- `require_session_auth` (and
the app-wide `require_lan_client`) are typed on `HTTPConnection`, the common
base of `Request` and `WebSocket`, specifically so the one auth mechanism
covers this socket too rather than needing a second one invented here.
"""

import asyncio
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..agents.base import BaseAgent
from ..contracts import ChatInput, ChatOutput, Topics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatBridge(BaseAgent):
    """Singleton mesh connection for the web chat surface."""

    def __init__(self):
        super().__init__(name="web_chat_bridge")
        self._listeners: set[asyncio.Queue] = set()
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        await self.connect()
        await self.subscribe(
            Topics.CHAT_OUTPUT, self._on_chat_output, deliver_policy="new"
        )
        self._started = True

    async def _on_chat_output(self, data: dict) -> None:
        output = ChatOutput.model_validate(data)
        for queue in list(self._listeners):
            queue.put_nowait(output)

    def attach(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._listeners.add(queue)
        return queue

    def detach(self, queue: asyncio.Queue) -> None:
        self._listeners.discard(queue)

    async def send(self, text: str) -> str:
        turn_id = str(uuid.uuid4())
        await self.publish(
            Topics.CHAT_INPUT, ChatInput(text=text, turn_id=turn_id).model_dump()
        )
        return turn_id

    async def stop(self) -> None:
        self._started = False
        await super().stop()


bridge = ChatBridge()


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = bridge.attach()
    forward_task = asyncio.create_task(_forward(websocket, queue))
    try:
        while True:
            text = (await websocket.receive_text()).strip()
            if text:
                await bridge.send(text)
    except WebSocketDisconnect:
        pass
    finally:
        bridge.detach(queue)
        forward_task.cancel()
        try:
            await forward_task
        except asyncio.CancelledError:
            pass


async def _forward(websocket: WebSocket, queue: asyncio.Queue) -> None:
    while True:
        output = await queue.get()
        await websocket.send_json(output.model_dump())
