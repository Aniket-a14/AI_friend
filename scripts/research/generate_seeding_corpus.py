import json
import os
from datetime import datetime, timedelta, timezone

# Rich, personal chitchat and distractor templates modeling Aniket's everyday life (0 to 19 years)
ANIKET_DISTRACTOR_TEMPLATES = [
    "Ma asked me to bring some fresh vegetables from the local market in Kolkata.",
    "Discussing our high school mathematics project with my classmate in the afternoon.",
    "Spending the evening coding a simple arcade game in Python in my study room.",
    "We had a beautiful family dinner tonight celebrating my academic results.",
    "Talking to my childhood friends about our weekend cricket match in the streets of Kolkata.",
    "I tried making sweet rasgullas at home today, they turned out soft and spongy.",
    "Walking through the crowded streets near Victoria Memorial, enjoying the cool breeze.",
    "Ma is making delicious home-cooked meals, the whole house smells amazing.",
    "Studying late into the night for my college entrance examinations, feeling focused.",
    "Moving to Bangalore for my college was a major transition, the city is so vibrant.",
    "Talking with Priya at the university cafe about our upcoming research presentation.",
    "Discussing affective cognitive architectures and neural networks in the lab today.",
    "Walking around Cubbon Park in Bangalore with Priya, talking about our future dreams.",
    "I bought some traditional sweet rasgullas from a local Bengali sweet shop in Bangalore.",
    "Reviewing database query optimization techniques with my research project teammates.",
    "Listening to Ma's stories on the phone about our childhood home back in Kolkata.",
    "Priya and I spent the afternoon studying in the quiet library alcove.",
    "My high school friends and I are planning a reunion back in Kolkata during the holidays.",
    "Debugging a tricky concurrent thread pool issue in my cognitive simulation module.",
    "Enjoying a hot cup of tea while watching the rain wash over the streets of Bangalore.",
]

# Structured technical and autobiographical milestone templates distributed across 4 developmental stages
EPOCH_0_5_TEMPLATES = [
    "Childhood Milestone: I took my first toddler steps in our warm home in Kolkata, surrounded by Ma and Baba's laughter.",
    "Childhood Milestone: Tasting my first traditional sweet rasgulla, a delicious treat that became my absolute favorite.",
    "Childhood Milestone: Playing with wooden toys in the sunlit balcony, listening to Ma's sweet Bengali lullabies.",
    "Childhood Milestone: Drawing simple shapes with colorful crayons, feeling a spark of early cognitive curiosity.",
    "Childhood Milestone: Baba taking me for a walk near the local park, looking up at the beautiful clear blue sky.",
]

EPOCH_6_12_TEMPLATES = [
    "School Milestone: Enrolling in primary school in Kolkata, wearing my new uniform and feeling exceptionally proud.",
    "School Milestone: Winning a school mathematics puzzle competition, discovering my deep passion for logical reasoning.",
    "School Milestone: Playing street cricket with my childhood neighborhood friends, celebrating a hard-fought victory.",
    "School Milestone: A wonderful family summer holiday, eating fresh mangoes and visiting the grand Victoria Memorial.",
    "School Milestone: Sitting in the school library reading my first science fiction book, dreaming of building intelligent machines.",
]

EPOCH_13_18_TEMPLATES = [
    "Teenage Milestone: Writing my very first lines of Python code on Baba's old computer, watching the screen light up.",
    "Teenage Milestone: Transitioning to senior high school in Kolkata, joining the science stream to study physics and math.",
    "Teenage Milestone: Building a basic chat assistant model in my room, igniting my lifelong interest in computer science.",
    "Teenage Milestone: Late-night study sessions with my school friends, sharing snacks and discussing our future college plans.",
    "Teenage Milestone: Graduating high school with top honors, receiving congratulations from my proud family and teachers.",
]

EPOCH_19_TEMPLATES = [
    "Adulthood Milestone: Moving from Kolkata to Bangalore to start my freshman year of university, a major step forward.",
    "Adulthood Milestone: Joining the university's advanced research lab focused on affective cognitive architectures.",
    "Adulthood Milestone: Meeting Priya at the university cafe, starting a beautiful and deeply supportive relationship.",
    "Adulthood Milestone: Celebrating my first successful research paper publication with Priya, sharing a sweet rasgulla.",
    "Adulthood Milestone: Commencing my junior research internship in Bangalore, feeling completely aligned with my vocation.",
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
    print("📦 Generating 19-year developmental seeding corpus for Aniket...")
    print(f"   - Distractors: {num_distractors}")
    print(f"   - Milestones: {num_milestones}")

    now = datetime.now(timezone.utc)
    nineteen_years_seconds = 19 * 365 * 24 * 3600
    time_step_seconds = nineteen_years_seconds / max(1, num_distractors)

    corpus = []

    # 1. Compile 100,000 backdated distractors
    print("⏳ Backdating 100,000 chitchats over 19 years...")
    for i in range(num_distractors):
        template = ANIKET_DISTRACTOR_TEMPLATES[i % len(ANIKET_DISTRACTOR_TEMPLATES)]
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
    generate_corpus(100000, 10000)
