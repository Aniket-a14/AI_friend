"""
ACT-R spacing effect (Bucket 9, voice remediation Phase 3).

`_base_activation`'s `ln(recall_count) - d*ln(hours_since_last_recall + 1)`
core cannot distinguish a memory recalled five times across a month (spaced
practice) from one recalled five times in the last ten minutes (massed
practice) when both currently sit at the same recall count and the same time
since their last recall -- yet the spacing-effect literature (Cepeda et al.'s
meta-analyses; the original ACT-R formulation itself sums a power-law decay
over every individual past presentation) treats those as very different
memories. `_spacing_hours`/`_base_activation`'s new term closes that gap
using only what the schema actually stores (`created_at`, `last_recalled_at`,
`recall_count` -- no per-recall history table), which is an approximation of
the literal formula, not a reimplementation of it. See both docstrings for
exactly what is and is not being claimed.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.state.memory_store import MemoryStore, _ln

NOW = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)


def _store():
    return MemoryStore(MagicMock(), MagicMock())


# --------------------------------------------------------------------------
# _spacing_hours: when there is, and is not, a signal to measure
# --------------------------------------------------------------------------


def test_spacing_hours_is_none_with_a_single_recall():
    """One recall has no interval to measure a gap between -- fabricating a
    "spacing" value from a single data point would be a guess, not a signal."""
    store = _store()
    assert (
        store._spacing_hours(1, NOW - timedelta(days=30), NOW) is None
    )


def test_spacing_hours_is_none_with_no_creation_timestamp():
    """No first data point means no span to divide."""
    store = _store()
    assert store._spacing_hours(5, None, NOW) is None


def test_spacing_hours_is_none_with_no_last_recall_timestamp():
    store = _store()
    assert store._spacing_hours(5, NOW - timedelta(days=30), None) is None


def test_spacing_hours_is_none_when_the_span_is_non_positive():
    """A creation timestamp at or after the last recall is not a real span --
    e.g. a fallback-to-"now" creation timestamp racing the recall clock. This
    must degrade to "no signal", not a negative or zero-hour bonus."""
    store = _store()
    assert store._spacing_hours(3, NOW, NOW) is None
    assert store._spacing_hours(3, NOW + timedelta(hours=1), NOW) is None


def test_spacing_hours_divides_the_span_across_every_recall():
    """The one piece of real arithmetic this function does: creation-to-last-
    recall span, spread evenly across recall_count recalls."""
    store = _store()
    created = NOW - timedelta(hours=100)
    assert store._spacing_hours(5, created, NOW) == pytest.approx(20.0)


# --------------------------------------------------------------------------
# _base_activation: backward compatibility and the spacing bonus itself
# --------------------------------------------------------------------------


def test_no_spacing_signal_reproduces_the_pre_bucket_9_formula_exactly():
    """Every existing caller and every existing test tuned against the old
    4-argument formula. `spacing_hours=None` (the default) must not move a
    single existing score."""
    store = _store()
    args = (5, 10.0, 0.6, 0.2)
    old_formula = (
        _ln(args[0])
        - store.decay_rate * _ln(args[1] + 1.0)
        + 1.5 * args[2]
        + 0.15 * (1.0 - args[3])
    )
    assert store._base_activation(*args) == pytest.approx(old_formula)
    assert store._base_activation(*args, None) == pytest.approx(old_formula)


def test_a_spaced_memory_outscores_an_otherwise_identical_massed_one():
    """The whole point: same recall_count, same recency, same importance,
    same emotional distance -- the only thing that differs is how spread out
    the recalls were, and that alone must move the score."""
    store = _store()
    spaced = store._base_activation(5, 2.0, 0.5, 0.3, spacing_hours=200.0)
    massed = store._base_activation(5, 2.0, 0.5, 0.3, spacing_hours=0.1)
    assert spaced > massed


def test_the_spacing_bonus_cannot_be_negative():
    """A very short (but still positive and countable) spacing must add a
    small non-negative amount, never penalise a memory for being recalled
    close together -- that is what the existing recency term already does."""
    store = _store()
    with_tiny_spacing = store._base_activation(5, 2.0, 0.5, 0.3, spacing_hours=0.001)
    without_spacing_term = store._base_activation(5, 2.0, 0.5, 0.3, spacing_hours=None)
    assert with_tiny_spacing >= without_spacing_term


# --------------------------------------------------------------------------
# wiring: the archive-scoring call site actually reaches the new term
# --------------------------------------------------------------------------


def test_archive_row_activation_rewards_a_memory_spaced_across_creation():
    """`_archive_row_activation` is the simplest of the four call sites to
    exercise directly (synchronous, one dict in). Two rows, identical except
    for `created_at`, must not score identically."""
    store = _store()
    base_row = {
        "last_recalled_at": NOW,
        "recall_count": 4,
        "valence": 0.1,
        "emotional_weight": 0.2,
        "importance_score": 0.5,
    }
    spaced_row = {**base_row, "created_at": NOW - timedelta(days=60)}
    massed_row = {**base_row, "created_at": NOW - timedelta(minutes=10)}

    spaced_score, *_ = store._archive_row_activation(
        spaced_row,
        0.5,
        current_valence=0.0,
        current_arousal=0.5,
        current_cortisol=0.2,
        current_time=NOW,
    )
    massed_score, *_ = store._archive_row_activation(
        massed_row,
        0.5,
        current_valence=0.0,
        current_arousal=0.5,
        current_cortisol=0.2,
        current_time=NOW,
    )
    assert spaced_score > massed_score


def test_archive_row_activation_survives_a_missing_created_at():
    """A row with no creation timestamp at all (legacy data predating the
    column, or a parse failure) must still score, just without the bonus --
    the pre-existing `_as_aware_utc`-survives-malformed-input guarantee
    extended to the new field rather than a new failure mode."""
    store = _store()
    row = {
        "last_recalled_at": NOW,
        "recall_count": 4,
        "valence": 0.1,
        "emotional_weight": 0.2,
        "importance_score": 0.5,
        # no "created_at" key at all
    }
    score, *_ = store._archive_row_activation(
        row,
        0.5,
        current_valence=0.0,
        current_arousal=0.5,
        current_cortisol=0.2,
        current_time=NOW,
    )
    assert isinstance(score, float)
