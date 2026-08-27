"""
Minimal text chat with your friend, over the real mesh.

    cd backend
    ../.venv/bin/python -m scripts.talk          # macOS/Linux
    ../.venv/Scripts/python.exe -m scripts.talk  # Windows

Phase 2.4 of the community roadmap: there was no text path anywhere in this
codebase, and voice requires LiveKit + STT + TTS all healthy at once, which is
a lot to demand while iterating on a persona. This publishes real `ChatInput`
onto `chat.input` and renders the real `ChatOutput` stream that comes back --
the actual cognitive pipeline (memory, affect, everything), unlike Phase 2.2's
wizard preview, which only ever talks to the raw LLM with no mesh involved.

Requires NATS and `brain_agent` running (`system_agent` for ticks and
`subconscious_agent` for reflection are not required for a single reply, but
without them nothing about the conversation persists between turns).

`scripts/testing/simulate_chat.py` is the one-shot ancestor of this script and
has two bugs this one doesn't repeat: it reads `response.get("chunk")`, a
field `ChatOutput` has never had (the real field is `content`), and it
hardcodes `"chat.input"`/`"chat.output"` instead of `Topics`.
"""

import asyncio
import os
import sys
import uuid

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from app.agents.base import BaseAgent
from app.contracts import ChatInput, ChatOutput, Topics

RESPONSE_TIMEOUT_S = 60.0


class TalkClient(BaseAgent):
    """A `BaseAgent` whose only job is to publish `chat.input` and hand every
    `chat.output` chunk to whoever's waiting for the current turn."""

    def __init__(self):
        super().__init__(name="talk_repl")
        self.incoming: asyncio.Queue[ChatOutput] = asyncio.Queue()

    async def _on_chat_output(self, data: dict) -> None:
        await self.incoming.put(ChatOutput.model_validate(data))


async def _say(client: TalkClient, text: str) -> None:
    turn_id = str(uuid.uuid4())
    await client.publish(Topics.CHAT_INPUT, ChatInput(text=text, turn_id=turn_id).model_dump())

    print("friend> ", end="", flush=True)
    said_anything = False
    while True:
        try:
            output = await asyncio.wait_for(client.incoming.get(), timeout=RESPONSE_TIMEOUT_S)
        except TimeoutError:
            if not said_anything:
                print("[no response -- is brain_agent running?]")
            else:
                print("\n[stream stalled]")
            return

        if output.turn_id and output.turn_id != turn_id:
            continue  # a chunk from a different (e.g. proactive) turn

        if output.content:
            print(output.content, end=" ", flush=True)
            said_anything = True

        if output.generation_error:
            print(f"\n[error: {output.generation_error}]", end="")

        if output.done:
            print()
            return


async def main() -> int:
    client = TalkClient()
    await client.connect()
    await client.subscribe(Topics.CHAT_OUTPUT, client._on_chat_output, deliver_policy="new")

    print("Talking to your friend. Blank line or Ctrl+C to quit.\n")
    try:
        while True:
            try:
                text = input("you> ").strip()
            except EOFError:
                break
            if not text:
                break
            await _say(client, text)
    finally:
        await client.stop()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nBye.")
