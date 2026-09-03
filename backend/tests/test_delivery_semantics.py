"""Phase 1E: the delivery-semantics checker
(scripts/diagnostics/check_delivery_semantics.py) is CI enforcement, so it
needs to prove it actually catches the defect classes it exists for -- a
mislabeled, missing, orphaned, or stale-override subject must each fail it,
matching check_subject_wiring.py's own "the check tests itself" convention.
"""

import sys
from pathlib import Path

DIAGNOSTICS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "diagnostics"
if str(DIAGNOSTICS_DIR) not in sys.path:
    sys.path.insert(0, str(DIAGNOSTICS_DIR))

import check_delivery_semantics as checker

from app.contracts import TOPIC_DELIVERY, Topics


def test_the_real_repository_passes_clean():
    """Regression guard: if this starts failing, either TOPIC_DELIVERY has
    genuinely drifted from nats_streams.py's stream tiers, or a new
    deliberate override needs to be added to DOCUMENTED_OVERRIDES -- not the
    check silently going warn-only."""
    assert checker.main() == 0


def test_every_topics_member_has_a_delivery_entry():
    assert set(TOPIC_DELIVERY.keys()) == set(Topics)


def test_audio_subjects_default_to_best_effort():
    assert checker.derive_default("audio.stream") == "best_effort"
    assert checker.derive_default("audio.stop") == "best_effort"


def test_non_audio_ai_messages_subjects_default_to_durable():
    assert checker.derive_default("chat.output") == "durable"
    assert checker.derive_default("state.update") == "durable"


def test_a_subject_matching_no_stream_has_no_default():
    assert checker.derive_default("nonexistent.subject") is None


def test_a_mislabeled_subject_is_caught(monkeypatch):
    """A subject on the durable AI_MESSAGES tier mislabeled as best_effort
    (not one of the two documented overrides) must fail the check."""
    mutated = dict(checker.TOPIC_DELIVERY)
    mutated[Topics.CHAT_OUTPUT] = "best_effort"
    monkeypatch.setattr(checker, "TOPIC_DELIVERY", mutated)
    assert checker.main() == 1


def test_a_missing_topics_entry_is_caught(monkeypatch):
    mutated = dict(checker.TOPIC_DELIVERY)
    del mutated[Topics.CHAT_OUTPUT]
    monkeypatch.setattr(checker, "TOPIC_DELIVERY", mutated)
    assert checker.main() == 1


def test_a_stale_override_is_caught(monkeypatch):
    """AGENT_VOICE_MODULATION is a documented override precisely because its
    declared value disagrees with its stream-tier default. If the declared
    value is changed to match the default, the override is now
    unjustified -- the check must say so rather than silently accept it."""
    mutated = dict(checker.TOPIC_DELIVERY)
    mutated[Topics.AGENT_VOICE_MODULATION] = checker.derive_default(
        Topics.AGENT_VOICE_MODULATION.value
    )
    monkeypatch.setattr(checker, "TOPIC_DELIVERY", mutated)
    assert checker.main() == 1
