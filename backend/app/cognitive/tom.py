"""
Theory of Mind (ToM) Modeling Layer — Phase 5.
Maintains separate representations of the user's inferred emotional state,
implied goals, and known concepts.
"""

import re
from typing import List
from pydantic import BaseModel


class UserMentalModel(BaseModel):
    """
    Representation of the user's mental state separate from the agent's internal state.
    Designed to be lightweight and serializable.
    """

    inferred_valence: float = 0.0  # -1.0 (negative) to 1.0 (positive)
    inferred_arousal: float = 0.5  # 0.0 (calm) to 1.0 (excited/angry)
    implied_goals: List[str] = []  # List of user's inferred immediate goals
    known_concepts: List[
        str
    ] = []  # Unique case-insensitive list of concepts user knows/mentioned


def update_known_concepts(current_concepts: List[str], user_input: str) -> List[str]:
    """
    Zero-overhead vocabulary tracker.
    Extracts significant words from the user's transcript without LLM latency.
    """
    if not user_input:
        return current_concepts

    # Extract clean alphabetical words between 4 and 15 characters in length
    words = re.findall(r"\b[a-zA-Z]{4,15}\b", user_input.lower())

    # High-frequency stop words to filter out
    stop_words = {
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
        "about",
        "would",
        "their",
        "about",
        "could",
        "should",
        "would",
        "about",
    }

    updated = list(current_concepts)
    for word in words:
        if word not in stop_words and word not in updated:
            updated.append(word)

    return updated
