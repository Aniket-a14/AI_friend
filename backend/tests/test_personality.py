import unittest
from unittest.mock import patch, MagicMock
import json
import os
from app.llm import LLMService

class TestPersonality(unittest.TestCase):
    @patch('app.llm.genai.Client')
    def test_personality_loading(self, mock_client):
        llm = LLMService()
        self.assertNotEqual(llm.personality, "<<<PERSONALITY_PLACEHOLDER>>>")
        self.assertIn("Pankudi", llm.personality)
        
        # Verify it's valid JSON
        try:
            json.loads(llm.personality)
        except json.JSONDecodeError:
            self.fail("Personality is not valid JSON string")

if __name__ == '__main__':
    unittest.main()
