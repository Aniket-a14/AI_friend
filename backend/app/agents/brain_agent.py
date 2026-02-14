import asyncio
import json
import logging
from typing import Dict, Any
from .base import BaseAgent
from ..llm.ollama_client import OllamaClient
from ..knowledge.graph_db import GraphDB
from ..memory_store import MemoryStore
from ..conversation_history_store import ConversationHistoryStore
from ..tools import ToolRegistry
from ..config import Config

logger = logging.getLogger(__name__)


class BrainAgent(BaseAgent):
    """
    The Brain Agent handles all text-based reasoning using local LLM.
    Orchestrates RAG, Tool Use, and Visual Context integration.
    """

    def __init__(
        self,
        ollama_url: str = Config.OLLAMA_URL,
        graph_db: GraphDB = None,
        memory_store: MemoryStore = None,
        conversation_store: ConversationHistoryStore = None,
        personality_config: Dict[str, Any] = None,
    ):
        super().__init__(name="brain_agent")
        self.ollama = OllamaClient(base_url=ollama_url)
        self.graph_db = graph_db
        self.memory_store = memory_store
        self.conversation_store = conversation_store
        self.tool_registry = ToolRegistry()
        if memory_store:
            self.tool_registry.set_memory_store(memory_store)

        self.personality = personality_config or {}
        self.history = []
        self.last_visual_context = "No visual data available."
        self.state = "idle"

    async def start(self):
        """Initialize and start the agent"""

        # Initialize History Store if present
        if self.conversation_store:
            await self.conversation_store.initialize()
            session_id = await self.conversation_store.start_session()
            logger.info(f"📜 Conversation logging active. Session: {session_id}")

        await self.connect()

        # Subscribe to chat input events
        await self.subscribe("chat.input", self._handle_chat_input)

        # Subscribe to visual frames (context only)
        await self.subscribe(
            "vision.frames", self._handle_vision_frame, deliver_policy="last"
        )
        
        # Start Autonomy Loop
        asyncio.create_task(self._autonomy_loop())

        logger.info(
            f"🧠 {self.name} started and listening to chat.input and vision.frames"
        )

    async def set_state(self, state: str):
        """Override to track local state."""
        self.state = state
        await super().set_state(state)

    async def _autonomy_loop(self):
        """Background task to check for silence and initiate conversation."""
        logger.info("🕰️ Autonomy loop started.")
        self.last_interaction_time = asyncio.get_event_loop().time()
        
        # Silence threshold in seconds
        SILENCE_THRESHOLD = 20.0 
        
        while True:
            await asyncio.sleep(5) # Check every 5s
            
            # If we are busy, don't interrupt
            if self.state != "idle":
                continue
            
            now = asyncio.get_event_loop().time()
            time_since_last = now - self.last_interaction_time
            
            if time_since_last > SILENCE_THRESHOLD:
                # Only initiate if we have some visual context to talk about
                # or just a random thought.
                logger.info(f"🕰️ Silence detected ({time_since_last:.1f}s). Initiating conversation...")
                await self._initiate_conversation()
                
                # Reset timer to prevent rapid-fire initiations
                self.last_interaction_time = asyncio.get_event_loop().time()

    async def _initiate_conversation(self):
        """Generate a self-initiated message based on context."""
        await self.set_state("thinking")
        
        # specialized prompt (bypass standard build_system_prompt for variety)
        # We want a short, natural "icebreaker"
        
        system_prompt = (
            f"You are {self.personality.get('name', 'AI Friend')}.\n"
            f"The user has been silent for a while.\n"
            f"CURRENT VISUALS: {self.last_visual_context}\n"
            f"EMOTIONAL PROSODY: You MUST use <emotion> tags.\n"
            f"TASK: seamlessly break the silence. Comment on what you see, or ask a gentle question.\n"
            f"DO NOT be annoying. Be warm and observant.\n"
            f"Keep it under 1 sentence."
        )
        
        full_response = ""
        # We pass a dummy user prompt to generate() because Ollama expects one
        # "..." acts as the silence trigger
        async for chunk in self.ollama.generate_stream("...", system=system_prompt):
             full_response += chunk
             await self.publish("chat.output", {"chunk": chunk, "done": False})
             
        await self.publish(
            "chat.output", {"chunk": "", "done": True, "full_response": full_response}
        )
        
        # Log this initiation
        if self.conversation_store:
             asyncio.create_task(self.conversation_store.log_message("assistant", full_response))
             
        self.history.append({"role": "assistant", "content": full_response})
        await self.set_state("idle")

    async def _handle_vision_frame(self, data: Dict[str, Any]):
        """Update the latest visual context (internal state)"""
        source = data.get("source", "unknown")
        # We could parse more details here if VisionAgent sent them
        self.last_visual_context = f"I am currently seeing the user's {source}."

    async def _handle_chat_input(self, message: Dict[str, Any]):
        """Handle incoming chat messages from the mesh"""
        # Reset silence timer
        self.last_interaction_time = asyncio.get_event_loop().time()
        
        user_text = message.get("text", "")
        if not user_text:
            return

        logger.info(f"💬 Processing: {user_text[:50]}...")

        # Log User Message (DB)
        if self.conversation_store:
            asyncio.create_task(self.conversation_store.log_message("user", user_text))

        await self.set_state("thinking")

        # 1. Long-term memory retrieval (RAG)
        memories = []
        if self.memory_store:
            memories = await self.memory_store.search_memories(user_text)

        # 2. Get GraphRAG context
        graph_context = await self._get_graph_context(user_text)

        # 3. Build system prompt
        context_str = (
            f"MEMORIES: {' | '.join(memories) if memories else 'None'}\n"
            f"VISION: {self.last_visual_context}\n"
            f"KNOWLEDGE_GRAPH: {graph_context}"
        )
        system_prompt = self._build_system_prompt(context_str)

        # 4. Generate and Stream response
        full_response = ""
        await self.set_state("speaking")

        async for chunk in self.ollama.generate_stream(user_text, system=system_prompt):
            full_response += chunk
            await self.publish("chat.output", {"chunk": chunk, "done": False})

        # 5. Finalize turn
        await self.publish(
            "chat.output", {"chunk": "", "done": True, "full_response": full_response}
        )
        
        # Reset timer again after talking
        self.last_interaction_time = asyncio.get_event_loop().time()

        # 6. Memory persistence (Async)
        if self.memory_store:
            asyncio.create_task(
                self.memory_store.add_memory(f"User: {user_text}\nMe: {full_response}")
            )

        # Log Assistant Message (DB)
        if self.conversation_store:
            asyncio.create_task(
                self.conversation_store.log_message("assistant", full_response)
            )

        # 7. Update conversation history
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": full_response})
        if len(self.history) > 10:
            self.history = self.history[-10:]

        await self.set_state("idle")
        logger.info(f"✅ Reasoning complete ({len(full_response)} chars)")

    async def _get_graph_context(self, text: str) -> str:
        """Fetch related knowledge from the GraphDB."""
        if not self.graph_db:
            return "No knowledge graph connected."
        # Simplified for now: just return a placeholder or implement basic search
        return "Knowledge graph search not yet optimized."

    def _build_system_prompt(self, context: str) -> str:
        """Construct the full system instruction with personality and tools."""
        personality_name = self.personality.get("name", "AI Friend")
        tools_str = json.dumps(self.tool_registry.get_definitions(), indent=2)

        return (
            f"You are {personality_name}, a warm and helpful AI friend.\n"
            f"ENVIRONMENT CONTEXT:\n{context}\n\n"
            f"AVAILABLE TOOLS:\n{tools_str}\n"
            f"If you need to use a tool, respond with: TOOL_CALL: name={{tool_name}} args={{...}}\n\n"
            f"CONVERSATION HISTORY:\n{json.dumps(self.history)}\n\n"
            f"EMOTIONAL PROSODY:\n"
            f"You are a living digital person. feel emotions.\n"
            f"You MUST wrap your response in an emotion tag to indicate your tone.\n"
            f"Options: 'neutral', 'happy', 'sad', 'serious', 'excited', 'warm'.\n"
            f"Format: <emotion type=\"happy\">I'm so glad to see you!</emotion>\n\n"
            f"Be concise, natural, and friendly. Speak like a close companion."
        )

    async def stop(self):
        """Shutdown the agent"""
        await super().stop()
        logger.info(f"🧠 {self.name} stopped")


async def main():
    # Instantiate stores
    # Note: MemoryStore requires a DB pool in real usage, skipping for this basic wiring step.

    # Simple wiring for ConversationHistoryStore
    history_store = ConversationHistoryStore()

    agent = BrainAgent(conversation_store=history_store)
    await agent.start()

    # Keep alive
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
