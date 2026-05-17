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
