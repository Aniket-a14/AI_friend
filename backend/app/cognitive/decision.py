import logging
import json
import re
from dataclasses import dataclass
from typing import Dict, Any
from .perception import CognitiveEvent
from .bt import Selector, Sequence, Action, Condition, NodeStatus
from ..config import Config

logger = logging.getLogger(__name__)

@dataclass
class ActionPlan:
    action_type: str  # e.g., "RESPOND_CHAT", "STORE_MEMORY", "BACKGROUND_CONSOLIDATION"
    payload: Dict[str, Any]
    goal: str
    priority: int = 1

class DecisionService:
    """
    The Decision Layer.
    Uses LLM-based Intent Classification and a Behavior Tree for goal selection.
    """
    def __init__(self, llm_service=None, memory_store=None):
        self.llm = llm_service
        self.memory = memory_store
        self.root = self._build_bt()

    def _build_bt(self):
        """Constructs the Behavior Tree."""
        return Selector("RootDecision", [
            Sequence("SystemTasks", [
                Condition("IsSystemTick", lambda b: b["event"].intent == "REFLECT"),
                Action("PlanReflection", self._plan_reflection)
            ]),
            Sequence("MemoryCommands", [
                Condition("IsRememberIntent", lambda b: b["event"].intent == "REMEMBER"),
                Action("PlanStorage", self._plan_storage)
            ]),
            Sequence("SocialReasoning", [
                Condition("IsChatIntent", lambda b: b["event"].intent == "CHAT"),
                Action("DetermineGoalAndResponse", self._plan_social_response)
            ])
        ])

    async def decide(self, event: CognitiveEvent, state_snapshot: Dict[str, Any]) -> ActionPlan:
        """
        Main decision loop.
        """
        # 1. Hybrid Routing: Fast Path for Greetings
        if self._is_simple_greeting(event.raw_content):
            event.intent = "CHAT"
            event.metadata["suggested_goal"] = "ENGAGE"
            event.metadata["preferred_model"] = Config.LLM_FAST_MODEL
        elif event.event_type == "USER_MESSAGE":
            # 2. Fast LLM-based Intent Classification (using 1B for speed)
            await self._classify_intent_and_goal(event, state_snapshot)
        
        # 3. Tick BT
        blackboard = {"event": event, "state": state_snapshot, "plan": None}
        status = await self.root.tick(blackboard)
        
        if status == NodeStatus.SUCCESS and blackboard["plan"]:
            return blackboard["plan"]
        
        return ActionPlan("RESPOND_CHAT", {"message": event.raw_content}, "ENGAGE")

    def _is_simple_greeting(self, text: str) -> bool:
        """Returns True if the text is a simple, common greeting."""
        greetings = {"hi", "hello", "hey", "hola", "namaste", "yo"}
        clean_text = text.lower().strip().strip("!").strip(".")
        return clean_text in greetings

    async def _classify_intent_and_goal(self, event: CognitiveEvent, state: Dict[str, Any]):
        """
        Uses LLM to classify intent and suggested goal.
        """
        prompt = f"""
        Analyze user input and current agent state.
        Input: "{event.raw_content}"
        Mood: {state['emotion']} (Valence: {state['mood']})
        
        Classify into:
        - intent: REMEMBER, CHAT, COMMAND
        - goal: COMFORT, INFORM, ENGAGE, TEASE, PROTECT
        
        Output JSON ONLY: {{"intent": "...", "goal": "..."}}
        """.strip()
        
        try:
            # Use 1B model for classification to keep latency < 50ms
            response = await self.llm.generate(prompt, model=Config.LLM_FAST_MODEL)
            
            # Find JSON in response
            json_str = response
            if "<think>" in response:
                json_str = response.split("</think>")[-1].strip()
            
            match = re.search(r'\{.*\}', json_str, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                event.intent = data.get("intent", event.intent)
                event.metadata["suggested_goal"] = data.get("goal", "ENGAGE")
                
                # If it's a simple CHAT, we can use 7B for quality, but for COMMAND/REMEMBER 1B is fine.
                event.metadata["preferred_model"] = Config.LLM_CHAT_MODEL if event.intent == "CHAT" else Config.LLM_FAST_MODEL
                logger.info(f"[Decision] Fast Classified: {data}")
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")

    # --- BT Actions ---

    def is_speculative_stop_confirmed(self, backbone_text: str, perception_keywords: list[str] = None) -> bool:
        """
        Hardened Semantic Conflict Resolver for CVS-1.0.
        Logic: Distinguish between Agent Commands and Conversational Context.
        """
        if not backbone_text:
            return False
            
        if perception_keywords is None:
            perception_keywords = ["stop", "wait", "hold", "listen", "sunno", "ruko", "quiet"] 
            
        clean_text = backbone_text.lower().strip()
        raw_words = clean_text.split()
        # Normalize: Strip common punctuation from words for exact matching
        words = [w.strip("!.,?;:") for w in raw_words]
        
        # 1. Contextual Filters (Reject stop if followed by these external objects/connectors)
        conversational_connectors = [
            "i agree", "i think", "i actually", "i just", "i am", "but", "though", "it is",
            "raining", "singing", "working", "playing", "for", "to", "be"
        ]
        
        call_signs = ["hey", "friend", "listen"]
        
        for kw in perception_keywords:
            kw = kw.lower()
            if kw in words:
                idx = words.index(kw)
                
                # Check for Conversational Context (Connectors following)
                if idx + 1 < len(words):
                    next_words = " ".join(words[idx+1:idx+3])
                    if any(conn in next_words for conn in conversational_connectors):
                        logger.debug(f"[ConflictResolver] Rejected '{kw}' - Conversational context: '{next_words}'")
                        continue
                        
                # 2. Positional Intelligence
                # Stop word must be at start OR preceded only by call-signs
                is_pivot = (idx == 0) or all(words[w] in call_signs for w in range(idx))
                
                if not is_pivot:
                    logger.debug(f"[ConflictResolver] Rejected '{kw}' - Buried intent in: '{clean_text}'")
                    continue

                # 3. Concise Command Check
                if len(words) <= 4:
                    logger.info(f"[ConflictResolver] Stop CONFIRMED (Concise Command): '{kw}' in '{clean_text}'")
                    return True
                
                # Default case for keywords at the start of longer sentences
                if idx == 0:
                    logger.info(f"[ConflictResolver] Stop CONFIRMED (Pivot Match): '{kw}' in '{clean_text}'")
                    return True
                
        logger.warning(f"[ConflictResolver] Speculative stop REJECTED. Backbone text '{clean_text}' contradicts early perception.")
        return False

    async def _plan_social_response(self, blackboard: Dict[str, Any]) -> bool:
        event = blackboard["event"]
        goal = event.metadata.get("suggested_goal", "ENGAGE")
        
        blackboard["plan"] = ActionPlan(
            action_type="RESPOND_CHAT",
            goal=goal,
            payload={
                "message": event.raw_content,
                "emotion_state": blackboard["state"]["emotion"],
                "model": event.metadata.get("preferred_model"),
                "surfaced_memories": event.metadata.get("surfaced_memories", [])
            },
            priority=1
        )
        return True

    async def _plan_reflection(self, blackboard: Dict[str, Any]) -> bool:
        blackboard["plan"] = ActionPlan("BACKGROUND_CONSOLIDATION", {}, "REFLECT", 0)
        return True

    async def _plan_storage(self, blackboard: Dict[str, Any]) -> bool:
        blackboard["plan"] = ActionPlan("STORE_MEMORY", {"content": blackboard["event"].raw_content}, "RECALL", 2)
        return True

