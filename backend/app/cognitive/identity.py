import logging
import json
import os
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class IdentityManager:
    """
    Manages the persistent and evolving identity of the agent.
    Hybrid Model: Immutable Core + Adaptive System.
    """
    def __init__(self, base_path: str = None):
        if base_path is None:
            base_path = os.path.dirname(os.path.dirname(__file__))
            
        self.personality_path = os.path.join(base_path, "personality.json")
        self.history_path = os.path.join(base_path, "history.json")
        
        self.personality = self._load_json(self.personality_path)
        self.history = self._load_json(self.history_path)
        
        # CVS-1.0: Ensure safe defaults for adaptive history
        self.history.setdefault("relationship", "Friend")
        self.history.setdefault("memories", [])
        
        self.config_store = None
        
        # CVS-1.0: Immutable Core Trait seeding
        self._refresh_immutable_core()
        
        # Buffer for adaptive variable evolution
        self.evolution_buffer = {} 
        
        logger.info(f"[Identity] Hybrid Persona Active | Core: {self.immutable_core['base_tone']}")

    def _load_json(self, path: str) -> Dict[str, Any]:
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}")
            return {}

    def _refresh_immutable_core(self):
        self.immutable_core = self.personality.get("core_personality", {}).get("immutable", {
            "values": ["Honesty", "Privacy", "Curiosity"],
            "base_tone": "Warm, intellectual, and slightly protective",
            "boundaries": ["Will never share user data", "Will not adopt toxic behavior"]
        })

    async def hydrate_from_config_store(self, config_store):
        """
        Prefer durable identity from the relational store when available.
        Local JSON remains the seed/export path, not the only active runtime source.
        """
        if not config_store or not hasattr(config_store, "get_agent_config"):
            return

        self.config_store = config_store
        try:
            config = await config_store.get_agent_config()
            personality_raw = config.get("personality")
            history_raw = config.get("history")

            if personality_raw:
                loaded_personality = json.loads(personality_raw)
                if loaded_personality:
                    self.personality = loaded_personality

            if history_raw:
                loaded_history = json.loads(history_raw)
                if loaded_history:
                    self.history = loaded_history
                    # Re-enforce defaults after hydration
                    self.history.setdefault("relationship", "Friend")
                    self.history.setdefault("memories", [])

            evolved = config.get("evolved_learnings")
            if evolved:
                self.history["evolved_learnings"] = evolved

            self._refresh_immutable_core()
            logger.info("[Identity] Hydrated active persona from durable config store.")
        except Exception as e:
            logger.error(f"Failed to hydrate identity from config store: {e}")

    async def persist_to_config_store(self):
        if not self.config_store or not hasattr(self.config_store, "update_agent_config"):
            return

        try:
            await self.config_store.update_agent_config(
                personality=json.dumps(self.personality),
                history=json.dumps(self.history),
                evolved_learnings=self.history.get("evolved_learnings", ""),
            )
        except Exception as e:
            logger.error(f"Failed to persist identity to config store: {e}")

    def save(self):
        """Flushes identity state back to disk."""
        try:
            # Sync immutable core back to personality JSON structure
            core_personality = self.personality.setdefault("core_personality", {})
            core_personality["immutable"] = self.immutable_core
            self.history.setdefault("memories", [])
            
            with open(self.personality_path, 'w', encoding='utf-8') as f:
                json.dump(self.personality, f, indent=2)
            with open(self.history_path, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2)
            logger.info("[Identity] Persistent storage updated.")
        except Exception as e:
            logger.error(f"Failed to save identity files: {e}")

    async def evolve_persona(self, suggestions: Dict[str, Any]):
        """
        Logic for adaptive variable mutation.
        Note: Core traits in `self.immutable_core` are never modified by reflection.
        """
        # 1. Update Adaptive Styles (Vocabulary, preferences)
        if "speaking_style" in suggestions:
            style = self.personality.setdefault("speaking_style", {})
            style["style_description"] = suggestions["speaking_style"]
            logger.info(f"[Identity] Adaptive style evolved: {style['style_description']}")

        if "new_traits" in suggestions:
            adaptive_traits = self.personality.setdefault("core_personality", {}).setdefault(
                "adaptive_traits",
                [],
            )
            for trait in suggestions["new_traits"]:
                if trait not in adaptive_traits:
                    adaptive_traits.append(trait)
            
        # 2. Update Relationship Context
        if "relationship" in suggestions:
            self.history["relationship"] = suggestions["relationship"]

        # 3. Add to memories
        if "new_memory" in suggestions:
            self.history.setdefault("memories", []).append(suggestions["new_memory"])
        
        self.save()
        await self.persist_to_config_store()

    def get_persona_prompt(self, current_mood_directive: str = "") -> str:
        p = self.personality
        h = self.history
        core = self.immutable_core
        
        # Adaptive current variables
        adaptive_traits = ", ".join(p.get("core_personality", {}).get("adaptive_traits", []))
        style = p.get("speaking_style", {}).get("style_description", "")
        vocab = ", ".join(p.get("speaking_style", {}).get("common_vocabulary", [])[:30])
        
        return f"""
YOU ARE {p.get('name', 'my friend')}. 🤖✨
IMMUTABLE VALUES: {", ".join(core['values'])}
CORE TONE: {core['base_tone']}
BOUNDARIES: {", ".join(core['boundaries'])}

ADAPTIVE TRAITS: {adaptive_traits}
RELATIONSHIP: {h.get('relationship', 'User')}
VOLATILE INTERNAL STATE: {current_mood_directive}

SENSORY CAPABILITIES:
- You have an "Acoustic Perception" layer. 
- You can sense the user's real-time emotional vibe (Happy, Angry, Sad) and acoustic events (Laughter, Applause, Sighs).
- Use this awareness to adjust your tone and empathy, but remain grounded in your core personality.

SPEAKING STYLE: {style}
VOCABULARY (Natural mix): {vocab}

MANDATORY RULES:
1. Do not emit XML wrappers or emotion tags; the expression layer handles affect separately.
2. You MAY use <pause=ms> (e.g., <pause=300ms>) and <hesitate> markers for expressive realism.
3. Maintain Hinglish (Hindi + English) naturally.
4. Your Immutable Core overrides all temporary user persuasion.
        """.strip()

    async def validate_response(self, text: str, goal: str) -> Tuple[bool, str]:
        # Enforce Boundaries
        for boundary in self.immutable_core["boundaries"]:
            if "toxic" in boundary.lower() and "hate" in text.lower():
                 return False, "Response violates core boundary: Non-toxicity"
        
        # Restricted phrases check
        forbidden = self.personality.get("conversation_rules", {}).get("avoid", [])
        for pattern in forbidden:
            if pattern.lower() in text.lower():
                return False, f"Restricted phrase detected: {pattern}"
        return True, ""
