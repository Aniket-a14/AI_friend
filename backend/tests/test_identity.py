import pytest
import json
from unittest.mock import patch, mock_open
from app.cognitive.identity import IdentityManager


@pytest.fixture
def sample_personality():
    return {
        "name": "my friend",
        "core_personality": {"traits": ["Warm", "Caring"]},
        "conversation_rules": {"avoid": ["As an AI", "I am a language model"]},
        "speaking_style": {"common_vocabulary": ["arre", "yaar"]},
    }


@pytest.fixture
def sample_history():
    return {"relationship": "Trusted Friend", "memories": ["Meeting at college"]}


def test_identity_load(sample_personality, sample_history):
    m_open = mock_open(read_data=json.dumps(sample_personality))

    with patch("builtins.open", m_open):
        with patch("os.path.exists", return_value=True):
            manager = IdentityManager(base_path="/fake/path")
            assert manager.personality["name"] == "my friend"
            assert "Warm" in manager.personality["core_personality"]["traits"]


@pytest.mark.asyncio
async def test_persona_evolution_immediate(sample_personality, sample_history):
    # Test semi-static trait update (Relationship)
    with patch("builtins.open", mock_open()):
        with patch("os.path.exists", return_value=True):
            manager = IdentityManager(base_path="/fake/path")
            manager.personality = sample_personality
            manager.history = sample_history

            await manager.evolve_persona({"relationship": "Closer Friend"})
            assert manager.history["relationship"] == "Closer Friend"


@pytest.mark.asyncio
async def test_persona_evolution_adaptive(sample_personality, sample_history):
    # Test adaptive style update (Speaking Style)
    with patch("builtins.open", mock_open()):
        with patch("os.path.exists", return_value=True):
            manager = IdentityManager(base_path="/fake/path")
            manager.personality = sample_personality
            manager.history = sample_history

            await manager.evolve_persona({"speaking_style": "More sarcastic and witty"})
            assert (
                "sarcastic"
                in manager.personality["speaking_style"]["style_description"].lower()
            )


def test_persona_prompt_generation(sample_personality, sample_history):
    with patch("builtins.open", mock_open()):
        with patch("os.path.exists", return_value=True):
            manager = IdentityManager(base_path="/fake/path")
            manager.personality = sample_personality
            manager.history = sample_history

            prompt = manager.get_persona_prompt()
            assert "my friend" in prompt
            assert "Warm" in prompt
            assert "Trusted Friend" in prompt
