import json
from unittest.mock import mock_open, patch

import pytest

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

    with patch("builtins.open", m_open), patch("os.path.exists", return_value=True):
        manager = IdentityManager(base_path="/fake/path", persona_file=None)
        assert manager.personality["name"] == "my friend"
        assert "Warm" in manager.personality["core_personality"]["traits"]


@pytest.mark.asyncio
async def test_persona_evolution_immediate(sample_personality, sample_history):
    # Test semi-static trait update (Relationship)
    with patch("builtins.open", mock_open()):
        with patch("os.path.exists", return_value=True):
            manager = IdentityManager(base_path="/fake/path", persona_file=None)
            manager.personality = sample_personality
            manager.history = sample_history

            await manager.evolve_persona({"relationship": "Closer Friend"})
            assert manager.history["relationship"] == "Closer Friend"


@pytest.mark.asyncio
async def test_persona_evolution_adaptive(sample_personality, sample_history):
    # Test adaptive style update (Speaking Style)
    with patch("builtins.open", mock_open()):
        with patch("os.path.exists", return_value=True):
            manager = IdentityManager(base_path="/fake/path", persona_file=None)
            manager.personality = sample_personality
            manager.history = sample_history

            await manager.evolve_persona({"speaking_style": "More sarcastic and witty"})
            assert (
                "sarcastic"
                in manager.personality["speaking_style"]["style_description"].lower()
            )


@pytest.mark.asyncio
async def test_evolve_persona_rejects_a_bare_language_name_as_speaking_style(
    sample_personality, sample_history
):
    """A weak reflection model has been observed writing the literal name of
    a language ("Hinglish") into speaking_style instead of an actual
    description of how someone talks (.agents/CONTEXT.md's Bucket 7 entry).
    Persisting it would leave every future prompt describing this friend's
    voice as a bare noun with no descriptive content -- truncation alone
    (MAX_STYLE_DESCRIPTION) never catches this, since the string is short and
    perfectly valid. Must be rejected, leaving the prior value in place.
    """
    with patch("builtins.open", mock_open()):
        with patch("os.path.exists", return_value=True):
            manager = IdentityManager(base_path="/fake/path", persona_file=None)
            manager.personality = sample_personality
            manager.history = sample_history
            original_style = dict(manager.persona.speaking_style)

            await manager.evolve_persona({"speaking_style": "Hinglish"})

            assert manager.persona.speaking_style == original_style


@pytest.mark.asyncio
async def test_evolve_persona_rejects_non_latin_speaking_style(
    sample_personality, sample_history
):
    """A weak reflection model has been observed writing CJK fragments into
    speaking_style on a persona authored entirely in English
    (.agents/CONTEXT.md's Bucket 7 entry) -- a language leak that truncation
    alone never catches, since the string is perfectly valid. Must be
    rejected rather than persisted.
    """
    with patch("builtins.open", mock_open()):
        with patch("os.path.exists", return_value=True):
            manager = IdentityManager(base_path="/fake/path", persona_file=None)
            manager.personality = sample_personality
            manager.history = sample_history
            original_style = dict(manager.persona.speaking_style)

            await manager.evolve_persona({"speaking_style": "更加放松和随意"})

            assert manager.persona.speaking_style == original_style


def test_persona_prompt_generation(sample_personality, sample_history):
    """The prompt must reflect the personality the manager actually loaded.

    This used to assign `manager.personality` *after* construction and rely on
    the prompt re-reading that dict every call. The narrative fields now come
    from the validated `PersonaProfile` built at load time, so the personality
    has to be supplied through the file the manager reads — which is also what
    happens in production. Assigning the dict afterwards no longer changes who
    the agent is, and should not: that was the drift this unification removed.
    """
    with patch("builtins.open", mock_open(read_data=json.dumps(sample_personality))):
        with patch("os.path.exists", return_value=True):
            manager = IdentityManager(base_path="/fake/path", persona_file=None)
            manager.history = sample_history

            prompt = manager.get_persona_prompt()
            assert "my friend" in prompt
            assert "Warm" in prompt
            assert "Trusted Friend" in prompt
