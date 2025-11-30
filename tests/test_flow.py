import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from app.state_manager import StateManager, AppState
from app.llm import LLMService

class TestBackendFlow(unittest.TestCase):
    def setUp(self):
        self.state_manager = StateManager()

    def test_state_transitions(self):
        # Initial State
        self.assertEqual(self.state_manager.state, AppState.IDLE)

        # Wake Detected
        self.state_manager.wake_detected()
        self.assertEqual(self.state_manager.state, AppState.ACTIVE_SESSION)

        # Start Speaking
        self.state_manager.start_speaking()
        self.assertEqual(self.state_manager.state, AppState.SPEAKING)

        # Finish Speaking
        self.state_manager.finish_speaking()
        self.assertEqual(self.state_manager.state, AppState.ACTIVE_SESSION)

        # Session End
        self.state_manager.session_end()
        self.assertEqual(self.state_manager.state, AppState.IDLE)

    @patch('app.llm.genai.Client')
    def test_memory_management(self, mock_client):
        llm = LLMService()
        llm.add_to_memory("user", "Hello")
        llm.add_to_memory("assistant", "Hi")
        
        self.assertEqual(len(llm.memory), 2)
        self.assertEqual(llm.memory[0]["content"], "Hello")
        
        llm.clear_memory()
        self.assertEqual(len(llm.memory), 0)

    @patch('app.llm.genai.Client')
    def test_memory_limit(self, mock_client):
        llm = LLMService()
        for i in range(10):
            llm.add_to_memory("user", str(i))
            
        self.assertEqual(len(llm.memory), 8)
        self.assertEqual(llm.memory[-1]["content"], "9")
        self.assertEqual(llm.memory[0]["content"], "2")

if __name__ == '__main__':
    unittest.main()
