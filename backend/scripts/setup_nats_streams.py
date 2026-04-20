"""
Setup NATS JetStream streams for AI Friend
"""

import asyncio
import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.nats_streams import setup_streams as _setup_streams


async def setup_streams(nats_url: str = None):
    nats_url = nats_url or os.getenv("NATS_URL", "nats://localhost:4222")
    print(f"🚀 Connecting to NATS at {nats_url}...")
    await _setup_streams(nats_url=nats_url)
    print("✨ NATS mesh infrastructure ready!")


if __name__ == "__main__":
    asyncio.run(setup_streams())
