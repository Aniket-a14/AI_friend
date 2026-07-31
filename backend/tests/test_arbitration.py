import pytest

from app.cognitive.decision import DecisionService


@pytest.fixture
def decision_service(mock_llm_service, mock_memory_store):
    return DecisionService(llm_service=mock_llm_service, memory_store=mock_memory_store)


@pytest.mark.parametrize(
    "backbone_text, perception_keywords, expected_confirmed",
    [
        # Positive Case: Intent is confirmed
        ("Stop right now.", ["stop"], True),
        ("Wait, silence please.", ["wait", "silence"], True),
        # Negative Case: Semantic conflict (False Positive)
        ("Wait, I actually agree with your point.", ["wait"], False),
        ("Stop raining please, it is so wet outside.", ["stop"], False),
        # Neutral Case: No stop words
        ("How are you doing?", ["stop"], False),
        # Mixed Case: Key is present but context is conversational
        ("I don't think we should stop here.", ["stop"], False),
        # Boundary Cases
        ("Alex, quiet.", ["alex", "quiet"], True),
        ("Don't be so quiet.", ["quiet"], False),
    ],
)
def test_speculative_stop_arbitration(
    decision_service, backbone_text, perception_keywords, expected_confirmed
):
    """
    Verify the Semantic Conflict Resolver can distinguish between a command and a conversational remark.
    """
    confirmed = decision_service.is_speculative_stop_confirmed(
        backbone_text, perception_keywords
    )
    assert confirmed == expected_confirmed


def test_conflict_resolver_empty_inputs(decision_service):
    """Edge case: Empty strings or None inputs."""
    assert decision_service.is_speculative_stop_confirmed("", ["stop"]) is False
    assert decision_service.is_speculative_stop_confirmed("Hello", None) is False


def test_conflict_resolver_case_insensitivity(decision_service):
    """Verify Case Insensitivity."""
    assert decision_service.is_speculative_stop_confirmed("STOP!!", ["stop"]) is True
    assert (
        decision_service.is_speculative_stop_confirmed("wait for it", ["WAIT"]) is False
    )  # Conversational
