"""
Setup NATS JetStream streams for AI Friend
"""
import asyncio
import nats
from nats.js.errors import BadRequestError

async def setup_streams():
    print("🚀 Connecting to NATS...")
    nc = await nats.connect("nats://localhost:4222")
    js = nc.jetstream()
    
    streams = [
        {"name": "CHAT", "subjects": ["chat.>"], "retention": "limits"},
        {"name": "AUDIO", "subjects": ["audio.>"], "retention": "interest"},
        {"name": "VISION", "subjects": ["vision.>"], "retention": "limits"},
        {"name": "STATE", "subjects": ["state.>"], "retention": "limits"}
    ]

    for stream in streams:
        config = nats.js.api.StreamConfig(
            name=stream["name"],
            subjects=stream["subjects"],
            retention=stream["retention"],
            max_msgs=5000,
            max_bytes=100_000_000
        )
        try:
            await js.add_stream(config)
            print(f"✅ Created {stream['name']} stream")
        except nats.js.errors.BadRequestError:
            # Likely already exists, try update
            try:
                await js.update_stream(config)
                print(f"🔄 Updated {stream['name']} stream")
            except Exception as e:
                print(f"❌ Failed to update {stream['name']}: {e}")
        except Exception as e:
            print(f"⚠️ Error with {stream['name']}: {e}")

    # List streams to verify
    try:
        current_streams = await js.streams_info()
        print(f"📊 Active Streams: {[s.config.name for s in current_streams]}")
    except:
        pass

    await nc.close()
    print("✨ NATS mesh infrastructure ready!")

if __name__ == "__main__":
    asyncio.run(setup_streams())
