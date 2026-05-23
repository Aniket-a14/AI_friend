import json
import os
from datetime import datetime, timedelta, timezone

# Standard, generic everyday conversation templates
GENERIC_DISTRACTOR_TEMPLATES = [
    "Hello, how is your day going?",
    "I am currently working on a software engineering project.",
    "The weather today is exceptionally clear and pleasant.",
    "Can you help me verify the database connection parameters?",
    "Let's schedule a meeting to discuss the system architecture.",
    "I prefer using standard, structured JSON files for data storage.",
    "What are the best practices for optimizing SQL query performance?",
    "We need to write unit tests to validate the new modules.",
    "The performance analysis shows a steady retrieval latency.",
    "It is important to maintain clean, well-documented codebases.",
]

# Structured technical milestone templates segmented into 4 developmental epochs (Ages 0 to 19)
EPOCH_0_5_TEMPLATES = [
    "Bootstrap Parameter: Core memory index initialized successfully.",
    "Bootstrap Parameter: Relational graph constraints verified.",
    "Bootstrap Parameter: Secure network socket connection established.",
]

EPOCH_6_12_TEMPLATES = [
    "Initialization Parameter: Default database connection pool allocated.",
    "Initialization Parameter: Event broker topic subscription list updated.",
    "Initialization Parameter: Context-gating decision thresholds calibrated.",
]

EPOCH_13_18_TEMPLATES = [
    "Optimization Parameter: Constants-time query cache limits enforced.",
    "Optimization Parameter: Asynchronous thread pool bounds adjusted.",
    "Optimization Parameter: High-precision embedding vector normalization verified.",
]

EPOCH_19_TEMPLATES = [
    "Adulthood Parameter: Active memory decay coefficients dynamically stabilized.",
    "Adulthood Parameter: Multi-hop graph belief cache invalidation complete.",
    "Adulthood Parameter: Real-time SQL database active pruning transactions online.",
]


def generate_mock_vector(dim=768):
    """Generates a mock normalized unit vector."""
    import numpy as np

    vec = np.random.randn(dim)
    norm = np.linalg.norm(vec)
    if norm < 1e-6:
        vec = np.zeros(dim)
        vec[0] = 1.0
        return vec
    return (vec / norm).tolist()


def generate_corpus(num_distractors=100000, num_milestones=10000):
    """
    Procedurally compiles a 110,000-memory database:
    - 100,000 generic distractors backdated over a 19-year temporal timeline.
    - 10,000 structured system milestone records categorized into 4 epochs.
    """
    print("📦 Generating 19-year developmental seeding corpus...")
    print(f"   - Distractors: {num_distractors}")
    print(f"   - Milestones: {num_milestones}")

    now = datetime.now(timezone.utc)
    nineteen_years_seconds = 19 * 365 * 24 * 3600
    time_step_seconds = nineteen_years_seconds / max(1, num_distractors)

    corpus = []

    # 1. Compile 100,000 backdated distractors
    print("⏳ Backdating 100,000 daily distractors over 19 years...")
    for i in range(num_distractors):
        template = GENERIC_DISTRACTOR_TEMPLATES[i % len(GENERIC_DISTRACTOR_TEMPLATES)]
        content = f"{template} [Turn: {i}]"

        # Proportional backdating across a 19-year timeline
        elapsed = i * time_step_seconds
        created_time = now - timedelta(seconds=elapsed)

        corpus.append(
            {
                "content": content,
                "raw_content": content,
                "wing": "personal",
                "room": "distractor",
                "importance": 0.4,
                "emotion": 0.1,
                "valence": 0.0,
                "certainty": 0.9,
                "source": "system_seeder",
                "created_at": created_time.isoformat(),
                "epoch": "daily_chitchat",
            }
        )

    # 2. Compile 10,000 structured milestone memories distributed across 4 developmental stages
    print("🧠 Organizing 10,000 system milestones into 4 developmental epochs...")
    milestone_step_seconds = nineteen_years_seconds / max(1, num_milestones)

    for i in range(num_milestones):
        elapsed = i * milestone_step_seconds
        created_time = now - timedelta(seconds=elapsed)

        # Determine Eriksonian developmental epoch based on chronological time
        age = 19 - (elapsed / (365 * 24 * 3600))

        if age < 5.0:
            template = EPOCH_0_5_TEMPLATES[i % len(EPOCH_0_5_TEMPLATES)]
            stage, crisis, virtue = "Trust vs Mistrust", "Trust vs Mistrust", "Hope"
        elif age < 12.0:
            template = EPOCH_6_12_TEMPLATES[i % len(EPOCH_6_12_TEMPLATES)]
            stage, crisis, virtue = (
                "Industry vs Inferiority",
                "Industry vs Inferiority",
                "Competence",
            )
        elif age < 19.0:
            template = EPOCH_13_18_TEMPLATES[i % len(EPOCH_13_18_TEMPLATES)]
            stage, crisis, virtue = (
                "Identity vs Role Confusion",
                "Identity vs Role Confusion",
                "Fidelity",
            )
        else:
            template = EPOCH_19_TEMPLATES[i % len(EPOCH_19_TEMPLATES)]
            stage, crisis, virtue = (
                "Intimacy vs Isolation",
                "Intimacy vs Isolation",
                "Love",
            )

        content = f"{template} [Milestone ID: {i}]"

        corpus.append(
            {
                "content": content,
                "raw_content": content,
                "wing": "personal",
                "room": "milestone",
                "importance": 0.9,
                "emotion": 0.8,
                "valence": 0.8,
                "certainty": 1.0,
                "source": "system_seeder",
                "created_at": created_time.isoformat(),
                "epoch": stage,
                "crisis": crisis,
                "virtue": virtue,
            }
        )

    # Save to disk
    out_path = os.path.join(os.path.dirname(__file__), "flooded_seeding_corpus.json")
    print(f"💾 Saving compiled corpus to disk: {out_path}...")
    with open(out_path, "w") as f:
        json.dump(corpus, f, indent=2)
    print("✨ Corpus generation complete!")


if __name__ == "__main__":
    generate_corpus(200, 50)
