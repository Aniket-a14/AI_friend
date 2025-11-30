import asyncio
import os
import uuid
import logging
from dotenv import load_dotenv
from app.conversation_history_store import ConversationHistoryStore

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_history_store():
    # Ensure environment variables are set or use defaults
    # You might need to set these manually if not in .env
    # os.environ["POSTGRES_PASSWORD"] = "your_password" 
    
    store = ConversationHistoryStore()
    
    logger.info("Initializing store...")
    try:
        await store.initialize()
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        return

    logger.info("Starting session...")
    session_id = await store.start_session()
    logger.info(f"Session ID: {session_id}")

    logger.info("Logging messages...")
    await store.log_message("user", "Hello AI!")
    await store.log_message("assistant", "Hello User! How can I help?")
    await store.log_message("user", "Tell me a joke.")
    await store.log_message("assistant", "Why did the chicken cross the road?")

    logger.info("Retrieving history...")
    history = await store.get_session_history(session_id)
    for msg in history:
        print(f"[{msg['timestamp']}] {msg['role']}: {msg['content']}")

    logger.info("Ending session...")
    await store.end_session()

    logger.info("Retrieving all sessions...")
    sessions = await store.get_all_sessions()
    for sess in sessions:
        print(f"Session {sess['id']}: {sess['started_at']} - {sess['ended_at']}")

    await store.close()
    logger.info("Test complete.")

if __name__ == "__main__":
    try:
        asyncio.run(test_history_store())
    except KeyboardInterrupt:
        pass
