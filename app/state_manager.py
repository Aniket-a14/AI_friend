from enum import Enum
import logging

logger = logging.getLogger(__name__)

class AppState(Enum):
    IDLE = "IDLE"
    ACTIVE_SESSION = "ACTIVE_SESSION"
    SPEAKING = "SPEAKING"

class StateManager:
    def __init__(self):
        self._state = AppState.IDLE
        self._observers = []

    @property
    def state(self):
        return self._state

    def add_observer(self, callback):
        """Callback(new_state)"""
        self._observers.append(callback)

    def _set_state(self, new_state: AppState):
        if self._state != new_state:
            logger.info(f"State transition: {self._state} -> {new_state}")
            self._state = new_state
            self._notify_observers()

    def _notify_observers(self):
        for callback in self._observers:
            try:
                callback(self._state)
            except Exception as e:
                logger.error(f"Error in state observer: {e}")

    def wake_detected(self):
        if self._state == AppState.IDLE:
            self._set_state(AppState.ACTIVE_SESSION)

    def session_active(self):
        """Called when returning to listening mode from speaking"""
        self._set_state(AppState.ACTIVE_SESSION)

    def start_speaking(self):
        if self._state == AppState.ACTIVE_SESSION:
            self._set_state(AppState.SPEAKING)

    def finish_speaking(self):
        if self._state == AppState.SPEAKING:
            self._set_state(AppState.ACTIVE_SESSION)

    def session_end(self):
        self._set_state(AppState.IDLE)
