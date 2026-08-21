import asyncio
from unittest.mock import AsyncMock

import pytest

from app.cognitive.appraisal import AppraisalEngine


def test_semantic_drift_ignores_a_second_json_block_in_the_response():
    """H1 regression for `appraise_semantic_drift`: a greedy `\\{.*\\}` regex
    spans from the response's first `{` to its LAST `}`, so a model that
    appends a second JSON-looking aside after the real answer used to corrupt
    the parse and fall through to the sequential-float-extraction fallback
    instead of reading the model's actual appraisal values.
    """
    engine = AppraisalEngine(identity_core_values=[])
    llm_client = AsyncMock()
    llm_client.generate.return_value = (
        '{"goal_congruence": 0.7, "norm_alignment": 0.9, "expectedness": 0.2}\n'
        'For reference, a hostile example would look like {"goal_congruence": -1.0}.'
    )

    result = asyncio.run(
        engine.appraise_semantic_drift(
            user_utterance="thanks so much for your help",
            llm_client=llm_client,
            current_pad={"valence": 0.0, "arousal": 0.0, "dominance": 0.5},
        )
    )

    # target_p = goal_congruence = 0.7; new_p = 0.0 + 0.2 * (0.7 - 0.0) = 0.14
    # target_d = norm_alignment = 0.9; new_d = 0.5 + 0.2 * (0.9 - 0.5) = 0.58
    # If the parse instead fused both blocks (old greedy behavior), data stays
    # falsy and the function returns current_pad unchanged (0.0 / 0.5).
    assert result["valence"] == pytest.approx(0.14)
    assert result["dominance"] == pytest.approx(0.58)
