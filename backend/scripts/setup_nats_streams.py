"""
Setup NATS JetStream streams for AI Friend
"""

import asyncio
import os
import nats


CORE_STREAMS = {
    "AI_MESSAGES": [
        "chat.*",
        "vision.*",
        "state.*",
        "cmd.*",
        "voice.*",
        "system.*",
        "memory.*",
        "identity.*",
        "knowledge.*",
    ],
    "AI_AUDIO": ["audio.*"],
}


async def setup_streams(nats_url: str = None):
    nats_url = nats_url or os.getenv("NATS_URL", "nats://localhost:4222")
    print(f"🚀 Connecting to NATS at {nats_url}...")
    nc = await nats.connect(nats_url)

    try:
        jsm = nc.jsm()
    except Exception as e:
        print(f"❌ NATS management API unavailable: {e}")
        await nc.close()
        raise

    for stream_name, subjects in CORE_STREAMS.items():
        try:
            await jsm.add_stream(name=stream_name, subjects=subjects)
            print(f"✅ Created {stream_name} stream")
        except nats.js.errors.BadRequestError:
            try:
                info = await jsm.stream_info(stream_name)
                current_subjects = set(info.config.subjects or [])
                desired_subjects = set(subjects)
                if desired_subjects.issubset(current_subjects):
                    print(f"✅ {stream_name} already synchronized")
                    continue

                config = info.config
                config.subjects = list(current_subjects.union(desired_subjects))
                await jsm.update_stream(config)
                print(f"🔄 Updated {stream_name} subjects")
            except Exception as e:
                print(f"❌ Failed to update {stream_name}: {e}")
                raise
        except Exception as e:
            print(f"⚠️ Error with {stream_name}: {e}")
            raise

    await nc.close()
    print("✨ NATS mesh infrastructure ready!")


if __name__ == "__main__":
    asyncio.run(setup_streams())
