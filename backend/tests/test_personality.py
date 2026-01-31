import unittest
from unittest.mock import patch, MagicMock
import json
import os
from app.llm import LLMService

class TestPersonality(unittest.TestCase):
    @patch('app.llm.genai.Client')
    def test_personality_default(self, mock_client):
        llm = LLMService()
        # Default personality is simple before DB load
        self.assertEqual(llm.personality, "You are a helpful AI assistant.")

if __name__ == '__main__':
    unittest.main()
