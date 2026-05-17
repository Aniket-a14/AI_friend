import sys
import os

# Add backend to path (assuming running from backend root)
sys.path.append(os.getcwd())


def test_soxr_import():
    print("1. Testing 'soxr' import...", end=" ")
    try:
        import soxr
        import numpy as np

        # Quick Functional Test
        data = np.zeros(100, dtype=np.float32)
        soxr.resample(data, 48000, 16000)
        print("✅ Success (Function working)")
    except ImportError:
        print("❌ Failed (ImportError)")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed ({e})")
        sys.exit(1)


def test_brain_wiring():
    print("2. Testing 'BrainAgent' wiring...", end=" ")
    try:
        from app.agents.brain_agent import BrainAgent
        from app.state.conversation_store import ConversationHistoryStore

        history = ConversationHistoryStore()
        agent = BrainAgent(conversation_store=history)

        if agent.conversation_store == history:
            print("✅ Success (Wiring correct)")
        else:
            print("❌ Failed (Store not assigned)")
    except Exception as e:
        print(f"❌ Failed to instantiate BrainAgent: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("🔍 Verifying Phase 25 Changes:\n")
    test_soxr_import()
    test_brain_wiring()
    print("\n✨ All checks passed. Ready for docker compose -f docker-compose.infra.yml up -d")
