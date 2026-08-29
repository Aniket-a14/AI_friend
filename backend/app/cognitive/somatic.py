"""
Somatic Vision-Homeostasis — the appraiser that turns seeing into feeling.

Until this existed, vision was a captioner bolted onto the side of the system:
`VisualAppraisalService` turned frames into sentences, the brain stored the
sentence as prompt context, and nothing else happened. The agent could describe
a cup of cardamom tea in front of it and feel exactly nothing. This module is
the missing link between the visual pillar and the endocrine one.

It mirrors the acoustic pillar deliberately. There, SenseVoice perceives *how*
the user sounds and `StateService.apply_sensory_perception` folds that into
mood. Here, the VLM perceives *what the agent is looking at* and
`StateService.apply_somatic_perception` folds a recognised comfort into
valence and arousal. Same shape, different sense.

**Where the comforts come from.** Nothing here is hardcoded. `learning.py`
already extracts facts from conversation and tags each with a category, one of
which is `somatic`; those land in Neo4j as triplets. This module reads them
back. So the agent's comforts are *learned from its own life* — if it has never
discussed anything somatic, it recognises nothing and no spike ever fires. That
is a deliberate, honest cold start, matching the mental lexicon's design (B1:
no benchmark-fitted constants baked into a retrieval path).

**On the roadmap's dopamine equation.** `docs/FUTURE_FINETUNED_ADAPTER.md` §C
specifies `D_t = min(1.0, D_{t-1} + 0.25)` alongside a valence spike. Both now
happen literally: `apply_somatic_perception` lifts valence and arousal *and*
fires a real phasic dopamine burst. Dopamine is no longer a purely derived
quantity — it is a tonic term (the old `max(0, valence) * arousal`) plus a
decaying burst, so a reward can outlast the mood swing that accompanied it.
"""

import logging
import re
import time
from typing import Any

logger = logging.getLogger(__name__)

# Roadmap §C: a recognised somatic entity lifts valence and arousal, which
# raises the tonic dopamine term; the phasic burst is fired separately by
# `apply_somatic_perception` (SOMATIC_DOPAMINE_SPIKE). Deliberately smaller than
# an explicit user statement of affect: seeing a comfort is a gentle background
# warmth, not an emotional event.
SOMATIC_VALENCE_SPIKE = 0.15
SOMATIC_AROUSAL_SPIKE = 0.10

# A single frame naming several comforts should not stack into a euphoria
# spike; the effect saturates.
MAX_SOMATIC_SPIKE_MULTIPLIER = 2.0

# Seeing the same mug for ten minutes should not re-spike every appraisal
# interval. Habituation is already a principle elsewhere in this codebase
# (VLM_HABITUATION_THRESHOLD); this is the affective counterpart.
SOMATIC_REFRACTORY_SECONDS = 120.0

# How long the learned-comfort list is trusted before re-reading the graph.
SOMATIC_CACHE_TTL_SECONDS = 300.0

# Entity names shorter than this are too collision-prone to match on
# ("it", "he"), and single characters would match almost any description.
MIN_SOMATIC_TERM_LENGTH = 3


class SomaticAppraiser:
    """Recognises learned comfort objects in a visual description.

    Usage is two-step and intentionally cheap on the hot path: `refresh()`
    pulls the learned entities from the graph on a TTL, and `appraise()` is a
    pure string match against the cached set.
    """

    def __init__(self, graph_store=None, *, now_fn=time.time):
        self.graph = graph_store
        self._now = now_fn
        self._terms: dict[str, dict[str, Any]] = {}
        self._cache_loaded_at: float = 0.0
        self._last_spike_at: dict[str, float] = {}

    # -- learned vocabulary -------------------------------------------------

    def _cache_is_stale(self) -> bool:
        if not self._cache_loaded_at:
            return True
        return (self._now() - self._cache_loaded_at) >= SOMATIC_CACHE_TTL_SECONDS

    async def refresh(self, force: bool = False) -> int:
        """Reload learned somatic entities from the graph.

        Returns the number of terms known afterwards. A graph failure is never
        propagated: the agent should keep seeing and talking even when Neo4j is
        down, it simply stops feeling comfort at things until the graph returns.
        """
        if not force and not self._cache_is_stale():
            return len(self._terms)
        if not self.graph:
            self._cache_loaded_at = self._now()
            return len(self._terms)

        query = """
        MATCH (s)-[r]->(t)
        WHERE r.category = 'somatic'
        RETURN t.name AS name, coalesce(r.confidence, 1.0) AS confidence
        """
        try:
            rows = await self.graph.execute_query(query, {})
        except Exception as exc:
            logger.warning(
                "[Somatic] Could not refresh learned comforts from the graph; "
                "keeping %d cached term(s): %s",
                len(self._terms),
                exc,
            )
            return len(self._terms)

        terms: dict[str, dict[str, Any]] = {}
        for row in rows or []:
            name = (row or {}).get("name")
            if not isinstance(name, str):
                continue
            normalized = name.strip().lower()
            if len(normalized) < MIN_SOMATIC_TERM_LENGTH:
                continue
            confidence = (row or {}).get("confidence", 1.0)
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = 1.0
            terms[normalized] = {
                "name": name.strip(),
                "confidence": max(0.0, min(1.0, confidence)),
            }

        self._terms = terms
        self._cache_loaded_at = self._now()

        # M8: `_last_spike_at` otherwise grows forever - a term dropped from
        # the graph (renamed, decayed away) never leaves the refractory map.
        # Drop keys no longer in `_terms`, and any timestamp already outside
        # the refractory window (it's dead weight - `_in_refractory` would
        # reject it anyway).
        now = self._now()
        self._last_spike_at = {
            term: ts
            for term, ts in self._last_spike_at.items()
            if term in terms and (now - ts) < SOMATIC_REFRACTORY_SECONDS
        }

        logger.info("[Somatic] %d learned comfort term(s) loaded.", len(terms))
        return len(terms)

    @property
    def known_terms(self) -> list[str]:
        return sorted(self._terms)

    # -- recognition --------------------------------------------------------

    @staticmethod
    def _mentions(description: str, term: str) -> bool:
        """Whole-word containment, so "tea" does not fire on "steam"."""
        return re.search(rf"\b{re.escape(term)}\b", description) is not None

    def _in_refractory(self, term: str) -> bool:
        last = self._last_spike_at.get(term)
        if last is None:
            return False
        return (self._now() - last) < SOMATIC_REFRACTORY_SECONDS

    def appraise(self, description: str) -> dict[str, Any] | None:
        """Match a visual description against learned comforts.

        Returns None when nothing is recognised — the overwhelmingly common
        case, and the caller must treat it as "no evidence", never as a neutral
        reading to blend in (the same trap documented in
        `apply_sensory_perception`).
        """
        if not description or not self._terms:
            return None

        haystack = description.lower()
        matched = []
        for term, meta in self._terms.items():
            if not self._mentions(haystack, term):
                continue
            if self._in_refractory(term):
                logger.debug("[Somatic] '%s' still in refractory; no spike.", term)
                continue
            matched.append((term, meta))

        if not matched:
            return None

        now = self._now()
        for term, _meta in matched:
            self._last_spike_at[term] = now

        # Saturating, confidence-weighted. Two comforts are warmer than one but
        # not twice as warm, and a shakily-learned fact moves less than a firm one.
        multiplier = min(MAX_SOMATIC_SPIKE_MULTIPLIER, float(len(matched)))
        mean_confidence = sum(m["confidence"] for _t, m in matched) / len(matched)
        scale = multiplier * mean_confidence

        return {
            "entities": [m["name"] for _t, m in matched],
            "valence_spike": SOMATIC_VALENCE_SPIKE * scale,
            "arousal_spike": SOMATIC_AROUSAL_SPIKE * scale,
            "confidence": mean_confidence,
        }
