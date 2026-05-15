import logging
from enum import Enum
from typing import Dict, Any, Set, Optional

logger = logging.getLogger(__name__)

class VoicePlaybackState(Enum):
    IDLE = "IDLE"
    BUFFERING = "BUFFERING"
    PLAYING = "PLAYING"
    SPECULATIVE_PAUSE = "SPECULATIVE_PAUSE"
    INSERT_WINDOW = "INSERT_WINDOW"
    TRANSITION = "TRANSITION"
    COOLDOWN = "COOLDOWN"

class VoiceSystem:
    """
    Pure Logic for Voice Playback Orchestration.
    Manages state, generations, and fencing logic.
    """

    def __init__(self):
        self.state = VoicePlaybackState.IDLE
        self.generation = 0
        self.stopped_turn_ids: Set[str] = set()
        self.paused_utterance_id: Optional[str] = None

    def handle_stop(self, is_speculative: bool, turn_id: Optional[str], utterance_id: Optional[str]):
        """Logic for cessation requests."""
        if is_speculative:
            self.paused_utterance_id = utterance_id
            self.state = VoicePlaybackState.SPECULATIVE_PAUSE
            return "speculative_pause"
        else:
            self.generation += 1
            if turn_id:
                self.stopped_turn_ids.add(turn_id)
            self.paused_utterance_id = None
            self.state = VoicePlaybackState.IDLE
            return "final_stop"

    def handle_resume(self, utterance_id: str) -> bool:
        """Logic for resumption requests. Returns True if state changed."""
        if (self.paused_utterance_id and utterance_id 
            and utterance_id != self.paused_utterance_id):
            return False

        if self.state == VoicePlaybackState.SPECULATIVE_PAUSE:
            self.paused_utterance_id = None
            self.state = VoicePlaybackState.PLAYING
            return True
        return False

    def is_current_item(self, item: Dict[str, Any]) -> bool:
        """Fencing logic for async synthesis/playback items."""
        turn_id = item.get("turn_id")
        return (
            item.get("generation") == self.generation
            and turn_id not in self.stopped_turn_ids
        )

    def set_state(self, new_state: VoicePlaybackState):
        self.state = new_state
