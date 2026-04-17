import logging
import json
import os
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class IdentityManager:
    """
    Manages the persistent and evolving identity of the agent.
    Loads data from personality.json and history.json.
    """
    def __init__(self, base_path: str = None):
        if base_path is None:
            base_path = os.path.dirname(os.path.dirname(__file__))
            
        self.personality_path = os.path.join(base_path, "personality.json")
        self.history_path = os.path.join(base_path, "history.json")
        
        self.personality = self._load_json(self.personality_path)
        self.history = self._load_json(self.history_path)
        
        # Buffer for core trait evolution (simulating time-gap)
        self.core_trait_buffer = {} 
        
        logger.info(f"[Identity] Loaded dynamic persona from {self.personality_path}")

    def _load_json(self, path: str) -> Dict[str, Any]:
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}")
            return {}

    def save(self):
        """Flushes identity state back to disk."""
        try:
            with open(self.personality_path, 'w', encoding='utf-8') as f:
                json.dump(self.personality, f, indent=2)
            with open(self.history_path, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2)
            logger.info("[Identity] Persistent storage updated.")
        except Exception as e:
            logger.error(f"Failed to save identity files: {e}")

    async def evolve_persona(self, suggestions: Dict[str, Any]):
        """
        Logic for trait mutation.
        Semi-static traits change immediately.
        Core traits require a pattern (buffer).
        """
        # 1. Update Semi-static Traits (e.g. relationship status, mood biases)
        if "relationship" in suggestions:
            self.history["relationship"] = suggestions["relationship"]
            logger.info(f"[Identity] Relationship evolved: {self.history['relationship']}")

        # 2. Update Core Traits (Buffering logic)
        if "new_traits" in suggestions:
            for trait in suggestions["new_traits"]:
                self.core_trait_buffer[trait] = self.core_trait_buffer.get(trait, 0) + 1
                
                # Threshold for core change (e.g., must be suggested 5 times)
                if self.core_trait_buffer[trait] >= 5:
                    current_traits = self.personality.get("core_personality", {}).get("traits", [])
                    if trait not in current_traits:
                        current_traits.append(trait)
                        logger.info(f"[Identity] CORE TRAIT EVOLVED: {trait}")
                        self.core_trait_buffer[trait] = 0 # Reset
        
        # 3. Add to memories
        if "new_memory" in suggestions:
            self.history.get("memories", []).append(suggestions["new_memory"])
        
        self.save()

    def get_persona_prompt(self) -> str:
        p = self.personality
        h = self.history
        
        traits = ", ".join(p.get("core_personality", {}).get("traits", []))
        style = p.get("voice_style", {}).get("overall_feel", "")
        # Get more Hinglish vocabulary
        vocab = ", ".join(p.get("speaking_style", {}).get("common_vocabulary", [])[:40])
        
        memories = "\n".join([f"- {m}" for m in h.get("memories", [])[-10:]]) # last 10
        
        return f"""
YOU ARE {p.get('name', 'my friend')}. ⚖️📡🏙️🛡️
BIO: {h.get('origin', '')}
CORE TRAITS: {traits}
RELATIONSHIP: {h.get('relationship', '')}
VOICE STYLE: {style}
SPEAKING STYLE: {p.get('speaking_style', {}).get('style_description', '')}
VOCABULARY (Natural mix): {vocab}
RECENT MEMORIES:
{memories}

MANDATORY RULES:
1. Always wrap your text in <emotion type='...'>...</emotion> tags.
2. Maintain Hinglish (Hindi + English) naturally.
3. Be expressive but stay within your personality boundaries.
        """.strip()

    async def validate_response(self, text: str, goal: str) -> Tuple[bool, str]:
        # Minimal pattern validation for now
        forbidden = self.personality.get("conversation_rules", {}).get("avoid", [])
        for pattern in forbidden:
            if pattern.lower() in text.lower():
                return False, f"Restricted phrase detected: {pattern}"
        return True, ""
