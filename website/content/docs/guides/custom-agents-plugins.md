# Custom Agents & Mesh Extension

Because all agents communicate over NATS JetStream with typed Pydantic contracts, you can easily write custom worker agents in **Python** or **Rust** to add new capabilities (e.g. Home Assistant automation, Spotify playback, calendar sync).

---

## Writing a Python Worker Agent

Subclass `BaseAgent` from `backend/app/agents/base.py`:

```python
import asyncio
from app.agents.base import BaseAgent
from app.contracts import ChatOutput, Topics

class SpotifyAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="spotify_agent")

    async def start(self):
        await super().start()
        # Subscribe to chat output to trigger actions on specific commands
        await self.subscribe(Topics.CHAT_OUTPUT, self._on_chat_output)

    async def _on_chat_output(self, msg: ChatOutput):
        if "play some music" in msg.content.lower():
            self.logger.info("Triggering background music playback...")
            # Execute your custom integration here

if __name__ == "__main__":
    agent = SpotifyAgent()
    asyncio.run(agent.start())
```

---

## Registering New NATS Topics

1. Declare the topic string in `backend/app/contracts.py` under `Topics`.
2. Define the Pydantic payload schema.
3. Run the stream initialization script:
   ```bash
   python backend/scripts/bootstrap/setup_nats_streams.py
   ```
4. Verify complete wiring with the static linter:
   ```bash
   python backend/scripts/check_subject_wiring.py
   ```

