import pytest

from app.utils.segmentation import HybridSegmenter


@pytest.mark.parametrize(
    "word,chunk_len,expected",
    [
        ("hello.", 3, 0.8),
        ("hello,", 3, 0.4),
        ("plain", 8, 0.3),
        ("plain", 3, 0.0),
        ("hello?", 9, 1.1),
    ],
)
def test_score_split_point_expected_scores(word, chunk_len, expected):
    segmenter = HybridSegmenter(target_size=8)

    assert segmenter.score_split_point(word, chunk_len) == expected


def test_score_split_point_extreme_length_override():
    segmenter = HybridSegmenter(target_size=100)

    assert segmenter.score_split_point("no-punctuation", 13) == 1.0


def test_comma_at_production_target_size_reaches_exactly_the_flush_threshold():
    """Bucket 5 (VOICE_REMEDIATION_PLAN.md): production constructs
    HybridSegmenter(target_size=7) (brain_agent.py), and a comma/colon/
    semicolon (0.4) plus the at-or-past-target_size length pressure (0.3)
    sums to exactly 0.7 -- documents the precise value the caller's
    `score >= 0.7` check (not `>`) must actually catch, since the comma is
    the most natural prosodic boundary and previously could never trigger
    a split on its own at this size.
    """
    segmenter = HybridSegmenter(target_size=7)

    assert segmenter.score_split_point("well,", 7) == 0.7
