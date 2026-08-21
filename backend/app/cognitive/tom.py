"""
Theory of Mind (ToM) Modeling Layer — Phase 5.
Maintains separate representations of the user's inferred emotional state,
implied goals, and known concepts.
"""

import re

from pydantic import BaseModel, Field

# M7: hard cap on `known_concepts` so a multi-hour session can't grow the list
# (and its serialized state payload) without bound. Sliding-window eviction in
# `update_known_concepts` keeps the most recently mentioned concepts.
MAX_KNOWN_CONCEPTS = 200


class UserMentalModel(BaseModel):
    """
    Representation of the user's mental state separate from the agent's internal state.
    Designed to be lightweight and serializable.
    """

    inferred_valence: float = 0.0  # -1.0 (negative) to 1.0 (positive)
    inferred_arousal: float = 0.5  # 0.0 (calm) to 1.0 (excited/angry)
    implied_goals: list[str] = Field(
        default_factory=list
    )  # List of user's inferred immediate goals
    known_concepts: list[str] = Field(
        default_factory=list
    )  # Unique case-insensitive list of concepts user knows/mentioned
    user_beliefs: dict[str, str] = Field(
        default_factory=dict
    )  # Concept name -> user's subjective belief/understanding


def extract_belief_discrepancies(
    user_beliefs: dict[str, str], ground_truth: dict[str, str]
) -> dict[str, dict[str, str]]:
    """
    Compares user beliefs with ground truth facts to identify discrepancies/misconceptions.
    Returns a dictionary of discrepancies:
    {concept: {"user_belief": ..., "ground_truth": ...}}
    """
    discrepancies = {}
    for concept, belief in user_beliefs.items():
        truth = ground_truth.get(concept)
        if truth and truth.lower() != belief.lower():
            discrepancies[concept] = {"user_belief": belief, "ground_truth": truth}
    return discrepancies


def update_known_concepts(current_concepts: list[str], user_input: str) -> list[str]:
    """
    Zero-overhead vocabulary tracker.
    Extracts significant words from the user's transcript without LLM latency.
    """
    if not user_input:
        return current_concepts

    # Extract clean alphabetical words between 4 and 15 characters in length
    words = re.findall(r"\b[a-zA-Z]{4,15}\b", user_input)

    # High-frequency stop words to filter out (lowercase)
    stop_words_lower = {
        "them",
        "they",
        "their",
        "there",
        "these",
        "those",
        "this",
        "that",
        "with",
        "from",
        "your",
        "what",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "have",
        "has",
        "had",
        "been",
        "being",
        "were",
        "was",
        "will",
        "would",
        "should",
        "could",
        "about",
        "above",
        "after",
        "again",
        "against",
        "some",
        "more",
        "most",
        "other",
        "such",
        "than",
        "then",
        "very",
        "just",
        "here",
    }

    updated = list(current_concepts)
    seen_lower = {c.lower() for c in updated}

    for word in words:
        if word.lower() not in stop_words_lower and word.lower() not in seen_lower:
            updated.append(word)
            seen_lower.add(word.lower())

    # Sliding window: drop the oldest concepts once the cap is exceeded, so a
    # long session's vocabulary tracker still reflects what the user has
    # recently talked about rather than growing without bound.
    if len(updated) > MAX_KNOWN_CONCEPTS:
        updated = updated[-MAX_KNOWN_CONCEPTS:]

    return updated
