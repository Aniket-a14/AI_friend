"""Evidence (Phase 1A, §15 item 1): a typed unit of grounding with modality,
confidence, and provenance -- the thing last_visual_context as a plain
string can't carry."""

import time

from app.cognitive.evidence import Evidence
from app.contracts import SurfacedMemory


def test_two_evidence_instances_get_distinct_ids():
    """The default_factory must actually be called per-instance -- a bug
    here (e.g. a bare default instead of default_factory) would silently
    give every Evidence the same evidence_id."""
    a = Evidence(content="x", source="vision_agent", modality="vision")
    b = Evidence(content="x", source="vision_agent", modality="vision")
    assert a.evidence_id != b.evidence_id


def test_no_expiry_means_never_expired():
    e = Evidence(content="x", source="s", modality="text", expiry=None)
    assert e.is_expired() is False
    assert e.is_expired(now=time.time() + 10_000) is False


def test_expiry_in_the_past_is_expired():
    e = Evidence(content="x", source="s", modality="vision", expiry=time.time() - 1)
    assert e.is_expired() is True


def test_expiry_in_the_future_is_not_yet_expired():
    e = Evidence(content="x", source="s", modality="vision", expiry=time.time() + 100)
    assert e.is_expired() is False


def test_from_surfaced_memory_carries_content_and_score():
    mem = SurfacedMemory(
        content="the user's birthday is in March",
        raw_content="the user's birthday is in March",
        score=0.87,
    )
    evidence = Evidence.from_surfaced_memory(mem)
    assert evidence.content == "the user's birthday is in March"
    assert evidence.modality == "memory"
    assert evidence.confidence == 0.87
    assert evidence.provenance == "memory_store"


def test_from_surfaced_memory_clamps_out_of_range_score():
    """score isn't documented as bounded to [0,1] on SurfacedMemory itself --
    a caller could hand Evidence a raw ranking value larger than 1.0 (or
    negative). confidence must stay a valid probability regardless."""
    mem = SurfacedMemory(content="x", raw_content="x", score=5.0)
    assert Evidence.from_surfaced_memory(mem).confidence == 1.0

    mem_negative = SurfacedMemory(content="x", raw_content="x", score=-2.0)
    assert Evidence.from_surfaced_memory(mem_negative).confidence == 0.0


def test_from_surfaced_memory_survives_missing_created_at():
    """created_at is Optional on SurfacedMemory; a None must not raise
    inside the timestamp parse."""
    mem = SurfacedMemory(content="x", raw_content="x", created_at=None)
    evidence = Evidence.from_surfaced_memory(mem)
    assert evidence.timestamp > 0
