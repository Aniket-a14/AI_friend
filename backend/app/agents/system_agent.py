import asyncio
import logging
import time
from .base import BaseAgent
from ..config import Config

logger = logging.getLogger("system_agent")


class SystemAgent(BaseAgent):
    """
    The System Pulse Orchestrator.
    Emits periodic 'system.tick' events to drive mesh-wide state evolution.
    """

    def __init__(self, tick_interval: int = None):
        super().__init__(name="system_agent")
        self.tick_interval = tick_interval or Config.SYSTEM_TICK_INTERVAL
        self.is_active = False
        self.start_time = time.time()

    async def start(self):
        """Standard startup sequence."""
        await self.connect()
        self.is_active = True
        logger.info(
            f"⚡ {self.name} Online | Heartbeat Interval: {self.tick_interval}s"
        )
        asyncio.create_task(self._pulse_loop())

    async def _pulse_loop(self):
        """The core heartbeat loop."""
        while self.is_active:
            try:
                # 1. Prepare Tick Metadata
                now = time.time()
                uptime = now - self.start_time

                tick_data = {
                    "timestamp": now,
                    "uptime": uptime,
                    "interval": self.tick_interval,
                    "source": self.name,
                }

                # 2. Broadcast to Mesh
                await self.publish("system.tick", tick_data)
                logger.debug(f"[Pulse] system.tick broadcasted | Uptime: {uptime:.1f}s")

                # 3. Wait for next heartbeat
                await asyncio.sleep(self.tick_interval)

            except Exception as e:
                logger.error(f"[Pulse] Heartbeat failure: {e}")
                await asyncio.sleep(5)  # Cooldown on failure

    async def stop(self):
        self.is_active = False
        await super().stop()
        logger.info(f"⚡ {self.name} system heartbeat stopped.")


async def main():
    agent = SystemAgent()
    await agent.start()
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await agent.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
