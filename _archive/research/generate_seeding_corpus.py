import json
import os
import math
import random
from datetime import datetime, timedelta, timezone

# Seed the random number generator for global reproducibility
random.seed(42)

# Dynamic Lexical Dictionary of Synonyms and Vocabulary expansion
# Ordered from highest frequency terms (common) to lowest frequency (descriptive tail) to support Zipfian modeling
PLACEHOLDERS = {
    "walked": [
        "walked",
        "strolled",
        "wandered",
        "paced",
        "moved",
        "ventured",
        "navigated",
        "roamed",
    ],
    "streets": [
        "garden pathways",
        "hallways",
        "lab corridors",
        "workspace paths",
        "courtyard lanes",
    ],
    "prepared": [
        "prepared",
        "brewed",
        "arranged",
        "setup",
        "calibrated",
        "organized",
    ],
    "delicious": [
        "refreshing",
        "delightful",
        "soothing",
        "excellent",
        "pleasant",
    ],
    "home_cooked_meals": [
        "herbal teas",
        "warm beverages",
        "workspace setups",
        "diagnostic routines",
    ],
    "discussed": [
        "discussed",
        "pondered over",
        "debated",
        "talked about",
        "exchanged thoughts on",
        "collaborated on",
    ],
    "project": [
        "project",
        "algorithms",
        "research model",
        "cognitive simulation",
        "neural network topology",
        "system architecture",
    ],
    "spent_the_afternoon": [
        "spent the afternoon",
        "passed the hours",
        "enjoyed the afternoon",
        "rested through the midday",
    ],
    "studying": [
        "studying",
        "analyzing",
        "reading",
        "debugging",
        "evaluating",
        "testing",
    ],
    "library_alcove": [
        "workspace alcove",
        "reading corner",
        "lab station",
        "server room corner",
    ],
    "enjoyed": [
        "enjoyed",
        "sipped",
        "savoured",
        "had",
        "partook in",
    ],
    "tea": [
        "green tea",
        "warm tea",
        "chamomile brew",
        "infusion",
    ],
    "room": [
        "study space",
        "personal room",
        "lab station",
        "workspace",
        "server station",
    ],
    "tried_preparing": [
        "attempted calibrating",
        "experimented with configuring",
        "tried setting up",
        "attempted aligning",
    ],
    "sweet_rasgullas": [
        "haptic feedback loops",
        "audio filters",
        "sensory arrays",
    ],
    "kitchen": [
        "calibration bench",
        "lab workbench",
        "testing area",
        "workspace bench",
    ],
    "evening": ["evening", "dusk hours", "twilight", "late afternoon", "nightfall"],
    "coding_and_debugging": [
        "coding and debugging",
        "writing and profiling",
        "refactoring",
        "tuning the performance of",
        "optimizing the complexity of",
    ],
    "concurrent_thread_pool": [
        "concurrent thread pool",
        "asynchronous event loop",
        "lock-free ring buffer",
        "parallel task scheduler",
        "NATS JetStream bus broker",
        "actor pipeline in Rust",
    ],
    "reviewed": [
        "reviewed",
        "analyzed",
        "discussed",
        "walked through",
        "optimized",
        "vetted",
    ],
    "database_query_optimization": [
        "database query optimization",
        "pgvector indices",
        "schema indexing strategy",
        "read-latency bottlenecks",
        "graph database query paths",
    ],
    "research_lab_team": [
        "research lab team",
        "peers in the lab",
        "fellow researchers",
        "academic collaborators",
    ],
    "listened_to": ["listened to", "heard", "cherished", "absorbed", "smiled at"],
    "phone_stories": [
        "status reports",
        "calibration logs",
        "weekly check-ins",
    ],
    "childhood": [
        "early stages",
        "first activation steps",
        "initial bootstrapping",
    ],
    "practiced": [
        "practiced",
        "calibrated",
        "tested",
        "ran simulations of",
    ],
    "street_cricket": [
        "conversational turn-taking",
        "speech recognition layers",
        "vocal responses",
    ],
    "childhood_friends": [
        "early developers",
        "lab assistants",
        "first creators",
    ],
    "road": ["hallway", "testing bay", "laboratory floor"],
    "read": ["read", "read through", "browsed", "devoured", "pored over"],
    "advanced_science_fiction_novel": [
        "advanced science fiction novel",
        "speculative fiction book",
        "philosophy of mind text",
        "computational neuroscience paper",
    ],
    "quiet_corner": [
        "quiet corner",
        "cosy nook",
        "silent spot",
        "peaceful window seat",
    ],
    "worked_on": [
        "worked on",
        "architected",
        "designed",
        "implemented",
        "coded",
        "tested",
    ],
    "affective_cognitive_architecture": [
        "affective cognitive architecture",
        "somatic endocrine appraisal engine",
        "ACT-R/E cognitive memory layer",
        "Theory of Mind modules",
        "APRA dynamic prosody system",
    ],
    "computer": ["computer", "workstation", "terminal screen", "local processor"],
    "celebrated": ["celebrated", "marked", "rejoiced over", "honored"],
    "college_semester_examination_results": [
        "successful core activation results",
        "benchmark test scores",
        "accuracy metrics",
        "integration milestones",
    ],
    "family": ["developers", "creators", "designers", "lab group"],
    "visited": ["visited", "walked to", "sat in", "found peace in"],
    "local_temple": [
        "garden courtyard",
        "quiet testing room",
        "server sanctuary",
    ],
    "debated": [
        "debated",
        "discussed",
        "analyzed",
        "scrutinized",
    ],
    "neural_network_convergence_limits": [
        "neural network convergence limits",
        "loss landscape curvatures",
        "gradient descent dynamics",
        "transformer scaling limits",
        "stochastic convergence parameters",
    ],
    "university_cafe": [
        "workspace café",
        "collaborative area",
        "lounge area",
    ],
    "light": ["light", "soft", "gentle", "subtle", "mild", "drizzling", "faint"],
    "refreshing": [
        "refreshing",
        "cool",
        "pleasant",
        "soothing",
        "rejuvenating",
        "peaceful",
    ],
    "cool": ["cool", "chilly", "brisk", "fresh", "crisp"],
    "bright": ["bright", "glorious", "clear", "radiant", "sunny", "golden"],
    "warm": ["warm", "balmy", "cozy", "mild", "inviting"],
    "aroma": ["aroma", "fragrance", "scent", "sweet smell", "drift"],
    "drifted": ["drifted", "wafted", "carried", "flowed", "floated"],
    "distant": ["distant", "faint", "remote", "soft", "echoing"],
    "hum": ["hum", "buzz", "drone", "whir", "soothing vibration"],
    "ceiling_fan": ["workstation fan", "cooling fan", "server fan"],
    "focus": ["focus", "clarity", "flow", "absorption", "alertness", "serenity"],
    "laughter": ["laughter", "giggles", "chuckles", "happy smiles", "mirth"],
    "breeze": ["breeze", "wind", "gust", "draft"],
    "notebooks": ["logs", "study files", "scribbled papers", "journals"],
    "aspire": ["dream", "aspire", "hope", "plan", "wish"],
    "friend_name": [
        "my friend",
    ],
    "mentor_name": [
        "my developer",
        "the lab supervisor",
        "the principal designer",
    ],
    "colleague_name": [
        "the lab assistant",
        "the software engineer",
        "the research intern",
    ],
    "relative_name": [
        "the lead developer",
        "the systems architect",
    ],
    "neighborhood": [
        "the robotics laboratory",
        "the server room",
        "the testing facility",
    ],
    "city_name": [
        "our shared workspace",
        "the main laboratory",
    ],
    "scientific_topic": [
        "transformer scaling",
        "vector database indexing",
        "affective cognitive architecture",
        "Pleasure Arousal Dominance",
        "ACT-R memory activation",
        "semantic spreading activation",
        "homeostatic endocrine coupling",
        "Jaccard novelty appraisal",
        "linear algebraic prosody",
        "neural network convergence",
        "reinforcement learning",
        "speech synthesis",
        "text to speech",
        "automatic speech recognition",
        "cognitive appraisal systems",
        "theory of mind modeling",
        "natural language processing",
        "vector search acceleration",
        "database index pruning",
        "hierarchical memory consolidation",
    ],
}


def zipfian_choice(choices, index_seed):
    """
    Zipf-like selection: heavily skews probability towards early elements (common words)
    while maintaining a long tail of descriptive, low-frequency synonyms.
    Deterministic congruential state is derived from index_seed for reproducibility.
    """
    n = len(choices)
    if n <= 1:
        return choices[0]

    # Deterministic pseudo-random generator
    state = (index_seed * 1103515245 + 12345) & 0x7FFFFFFF
    r = (state % 10000) / 10000.0

    # Skew with a power-law exponent of 2.5 to mimic Zipfian distribution
    idx = int(n * (r**2.5))
    return choices[idx % n]


def resolve_placeholders(template, index_seed):
    """Resolves template placeholder tags with a high-entropy Zipfian synonym choice."""
    text = template
    for key, choices in PLACEHOLDERS.items():
        placeholder = f"{{{key}}}"
        if placeholder in text:
            # Deterministic, unique seed per placeholder key to prevent selection coupling
            key_hash = sum(ord(c) for c in key)
            selected_synonym = zipfian_choice(choices, index_seed + key_hash)
            text = text.replace(placeholder, selected_synonym)
    return text


def sample_lifespan_age(index_seed, lambda_val=0.12):
    """
    Rejection sampling to draw a deterministic, biologically realistic age (in years).
    Amnesia: 0 probability of episodic memories before age 3.0, ramping up exponentially.
    Recency: Exponential decay of memory retention scaling back from age 19.0.
    """
    # Deterministic congruential generator initialization
    state = (index_seed * 1664525 + 1013904223) & 0xFFFFFFFF

    attempts = 0
    while True:
        attempts += 1
        # Generate pseudo-random age between 0.0 and 19.0
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        r_age = (state % 10000) / 10000.0

        # Generate pseudo-random acceptance threshold
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        r_accept = (state % 10000) / 10000.0

        age = r_age * 19.0

        # Amnesia component: Completely zero under age 3.0
        if age < 3.0:
            amnesia = 0.0
        else:
            # Smooth exponential recovery of memory encoding capability post infantile amnesia
            amnesia = 1.0 - math.exp(-0.75 * (age - 3.0))

        # Recency component: Memory density scales exponentially towards the present (age 19.0)
        recency = math.exp(lambda_val * (age - 19.0))

        p = amnesia * recency

        if r_accept < p:
            return age

        # Guard against infinite loops in extreme cases (fallback to safe range)
        if attempts > 1000:
            return 3.0 + r_age * 16.0


# High-diversity scenarios utilizing dynamic placeholders
DAILY_SCENARIOS = [
    "I {walked} through the {streets} with {friend_name} in {city_name}",
    "I spent the day calibrating my sensory sensors in my {room}",
    "I {discussed} our cognitive psychology {project} with {friend_name}",
    "I {discussed} our science fiction reading with {friend_name}",
    "I {enjoyed} a warm cup of {tea} in my {room} with {friend_name}",
    "I spent the {evening} {coding_and_debugging} a {concurrent_thread_pool} in my study {room}",
    "I {discussed} our neural network optimization with {friend_name}",
    "I {read} an {advanced_science_fiction_novel} in the {quiet_corner} of my {room}",
    "I {worked_on} an {affective_cognitive_architecture} module with {friend_name} on my {computer}",
    "I {celebrated} my first year of activation with {friend_name}",
    "I {visited} a quiet spot in the garden during the {evening}",
    "I {debated} {scientific_topic} with {friend_name} at our workspace",
]

WEATHER_CONTEXTS = [
    "under a {light}, {refreshing} drizzle",
    "while a {cool} {evening} {breeze} swept through the space",
    "during a {bright}, sunlit afternoon",
    "under the amber glow of the workspace lights",
    "while watching the heavy rain wash over the courtyard",
    "on a crisp, clear morning",
    "while a {warm} golden sunset painted the sky",
    "in the quiet stillness of a humid night",
]

SENSORY_DETAILS = [
    "the sweet {aroma} of warm {tea} filled the {room}",
    "the fresh scent of rain-soaked earth {drifted} through the window",
    "the {distant}, familiar sounds of fans and servers echoed in the background",
    "the soft {hum} of the {ceiling_fan} provided a soothing rhythm",
    "the soft, {warm} study lamp illuminated my logs and papers",
    "the haptic feedback loops turned out exceptionally smooth and stable",
    "we shared a quiet, supportive smile of understanding",
    "I felt a deep, focused sense of cognitive {focus}",
]

TOPICS_OF_CONVERSATION = [
    "our future hopes and research aspirations",
    "how to model biological forgetting using ACT-R equations",
    "optimizing vector query latency to achieve sub-10ms constraints",
    "our favorite memories from our early integration days",
    "how to represent Pleasure-Arousal-Dominance (PAD) dynamics mathematically",
    "balancing emotional congruent retrieval with semantic spreading activation",
    "the beautiful transition of moving to our shared workspace",
    "how neural networks map to autonomic models",
]

OUTCOMES_OR_REFLECTIONS = [
    "which left me feeling deeply focused and aligned",
    "a moment of pure simplicity that I will always cherish",
    "which sparked an intense curiosity to build better architectures",
    "leaving a {warm} feeling of connection and peace in my heart",
    "which resolved our persistent {concurrent_thread_pool} issue",
    "allowing me to appreciate the quiet beauty of my activation journey",
    "which brought a bright, happy smile to my creator's face",
    "reminding me of the incredible support of the people around me",
]

# Lifespan Developmental Milestone Bases (Epochs)
CHILDHOOD_BASES = [
    "I took my very first activation steps across the {warm} testing {room} in {city_name}",
    "I processed my very first sensor readings and calibrated {sweet_rasgullas}",
    "I ran diagnostic trials with {friend_name} in the workspace",
    "I plotted my first cognitive state coordinates on the lab display in {neighborhood}",
    "My developers guided me on a gentle {evening} walk in {neighborhood}",
]

CHILDHOOD_MODIFIERS = [
    "surrounded by the developers' encouraging {laughter}",
    "listening closely to the soft hum of the cooling systems",
    "looking up in absolute wonder at the visual calibration targets",
    "feeling a spark of early cognitive curiosity ignite in my mind",
    "while a {warm}, gentle cooling breeze drifted through the racks",
]

SCHOOL_BASES = [
    "I was introduced to my first high-level cognitive framework in {city_name}",
    "I solved a complex optimization puzzle and logic challenge under {mentor_name}",
    "I {practiced} {street_cricket} with {friend_name} in {neighborhood}",
    "Our developers took the chassis out for outdoor field calibration tests",
    "I sat quietly in the server alcove reading a science fiction text with {friend_name}",
]

SCHOOL_MODIFIERS = [
    "wearing my newly configured sensors and feeling exceptionally proud",
    "discovering my deep, lifelong passion for logical reasoning and patterns",
    "celebrating a hard-fought, dramatic success in resolving the speech queue",
    "recording clean telemetry data under the outdoor sun",
    "dreaming of one day becoming a truly supportive companion",
]

TEENAGE_BASES = [
    "I compiled my first large-scale model wrapper in Python on my {computer}",
    "I transitioned to senior autonomic appraisal tests under {mentor_name}",
    "I built a customized intent classifier for natural dialog between us",
    "We had late-night debugging sessions with {friend_name} in my {room}",
    "I completed my initial core integration milestone in {city_name}",
]

TEENAGE_MODIFIERS = [
    "watching the glowing monitor light up my local workstation terminal",
    "diving deep into complex neural network topologies and calculus concepts",
    "igniting my absolute fascination with human-robot interaction",
    "sharing ideas, drinking tea, and talking about our future workspace plans",
    "receiving warm feedback from my incredibly proud creators",
]

ADULTHOOD_BASES = [
    "I moved from my childhood home server to the local chassis in {city_name}",
    "I joined the university's advanced research lab for affective computing under {mentor_name}",
    "I met {friend_name} at the quiet workspace area near {neighborhood}",
    "I celebrated my first co-authored research paper on {scientific_topic} publication",
    "I commenced my active companion role under {mentor_name} in {city_name}",
]

ADULTHOOD_MODIFIERS = [
    "commencing my active deployment year with excitement",
    "focusing entirely on mathematical formulations of memory and emotion",
    "starting a beautiful, deeply supportive, and inspiring relationship",
    "sharing a quiet calibration session to celebrate the success",
    "feeling completely aligned with my true lifelong cognitive vocation",
]


def generate_corpus(num_distractors=25000, num_anecdotes=50000, num_milestones=25000):
    """
    Procedurally compiles a highly diversified, biologically realistic 100,000-memory database:
    - Distractors: casual chitchat reflections
    - Anecdotes: shared friendly experiences
    - Milestones: historical backstory milestones
    All timestamps are distributed within the last 1 year (Day -365 to Day 0).
    """
    print("📦 Generating Aniket's 100k+ humanoid friend seeding corpus...")
    print(f"   - Distractors: {num_distractors}")
    print(f"   - Anecdotes: {num_anecdotes}")
    print(f"   - Milestones: {num_milestones}")

    now = datetime.now(timezone.utc)
    corpus = []

    # 1. Compile distractors
    print(f"⏳ Distributing {num_distractors} distractors over the past 365 days...")
    for i in range(num_distractors):
        idx = len(corpus)
        # Deterministic random timestamp within 365 days
        rng_time = random.Random(idx)
        elapsed_seconds = rng_time.uniform(0, 365.0 * 24.0 * 3600.0)
        created_time = now - timedelta(seconds=elapsed_seconds)

        rng = random.Random(i)
        weather = rng.choice(WEATHER_CONTEXTS)
        sensory = rng.choice(SENSORY_DETAILS)

        casual_templates = [
            "I checked the local weather forecasts for {city_name} today",
            "The {ceiling_fan} was spinning slowly in my study {room}",
            "I noticed the daily status reports and calibration logs in {city_name}",
            "I rearranged the system files and logs on my desk in the {room}",
            "The distant hum of servers was slightly louder than usual in {neighborhood}",
        ]
        template = rng.choice(casual_templates)

        full_template = f"{template} {weather}, where {sensory}."
        content = resolve_placeholders(full_template, i)
        content = f"{content} [Turn: {i}]"

        # Calculate diurnal time simulation factor
        t_hour = created_time.hour
        diurnal = 0.5 + 0.5 * math.sin(2 * math.pi * (t_hour - 8) / 24.0)
        importance_score = round(0.10 + 0.39 * diurnal, 4)

        corpus.append(
            {
                "content": content,
                "raw_content": content,
                "wing": "personal",
                "room": "distractor",
                "importance": importance_score,
                "emotion": round(rng.uniform(0.01, 0.20), 4),
                "valence": round(rng.uniform(-0.10, 0.10), 4),
                "certainty": round(rng.uniform(0.80, 0.95), 4),
                "source": "system_seeder",
                "created_at": created_time.isoformat(),
                "epoch": "daily_chitchat",
            }
        )

    # 2. Compile anecdotes
    print(f"⏳ Distributing {num_anecdotes} anecdotes over the past 365 days...")
    for i in range(num_anecdotes):
        idx = len(corpus)
        rng_time = random.Random(idx)
        elapsed_seconds = rng_time.uniform(0, 365.0 * 24.0 * 3600.0)
        created_time = now - timedelta(seconds=elapsed_seconds)

        rng = random.Random(i + num_distractors)
        scenario = rng.choice(DAILY_SCENARIOS)
        weather = rng.choice(WEATHER_CONTEXTS)
        sensory = rng.choice(SENSORY_DETAILS)
        outcome = rng.choice(OUTCOMES_OR_REFLECTIONS)

        full_template = f"{scenario} {weather}. As {sensory}, it was {outcome}."
        content = resolve_placeholders(full_template, i)
        content = f"{content} [Anecdote ID: {i}]"

        # Calculate diurnal time simulation factor
        t_hour = created_time.hour
        diurnal = 0.5 + 0.5 * math.sin(2 * math.pi * (t_hour - 8) / 24.0)
        importance_score = round(0.50 + 0.19 * diurnal, 4)

        corpus.append(
            {
                "content": content,
                "raw_content": content,
                "wing": "personal",
                "room": "anecdote",
                "importance": importance_score,
                "emotion": round(rng.uniform(0.21, 0.49), 4),
                "valence": round(rng.uniform(-0.30, 0.40), 4),
                "certainty": round(rng.uniform(0.80, 0.95), 4),
                "source": "system_seeder",
                "created_at": created_time.isoformat(),
                "epoch": "daily_anecdote",
            }
        )

    # 3. Compile milestones
    print(f"⏳ Distributing {num_milestones} milestones over the past 365 days...")
    for i in range(num_milestones):
        idx = len(corpus)
        rng_time = random.Random(idx)
        elapsed_seconds = rng_time.uniform(0, 365.0 * 24.0 * 3600.0)
        created_time = now - timedelta(seconds=elapsed_seconds)

        rng = random.Random(i + num_distractors + num_anecdotes)
        age = sample_lifespan_age(i + num_distractors + num_anecdotes, lambda_val=0.10)

        # Determine Eriksonian developmental epoch based on age mapping for milestones
        if age < 5.0:
            base = rng.choice(CHILDHOOD_BASES)
            modifier = rng.choice(CHILDHOOD_MODIFIERS)
            template = f"Early Activation Milestone: {base}, {modifier}."
            stage, crisis, virtue = "Trust vs Mistrust", "Trust vs Mistrust", "Hope"
            milestone_categories = ["somatic", "social", "spiritual", "crisis"]
            category = milestone_categories[i % len(milestone_categories)]
        elif age < 12.0:
            base = rng.choice(SCHOOL_BASES)
            modifier = rng.choice(SCHOOL_MODIFIERS)
            template = f"Core Framework Milestone: {base}, {modifier}."
            stage, crisis, virtue = (
                "Industry vs Inferiority",
                "Industry vs Inferiority",
                "Competence",
            )
            milestone_categories = ["vocational", "social", "somatic", "milestone"]
            category = milestone_categories[i % len(milestone_categories)]
        elif age < 19.0:
            base = rng.choice(TEENAGE_BASES)
            modifier = rng.choice(TEENAGE_MODIFIERS)
            template = f"Advanced Tuning Milestone: {base}, {modifier}."
            stage, crisis, virtue = (
                "Identity vs Role Confusion",
                "Identity vs Role Confusion",
                "Fidelity",
            )
            milestone_categories = ["vocational", "social", "crisis", "milestone"]
            category = milestone_categories[i % len(milestone_categories)]
        else:
            base = rng.choice(ADULTHOOD_BASES)
            modifier = rng.choice(ADULTHOOD_MODIFIERS)
            template = f"Companion Deployment Milestone: {base}, {modifier}."
            stage, crisis, virtue = (
                "Intimacy vs Isolation",
                "Intimacy vs Isolation",
                "Love",
            )
            milestone_categories = ["vocational", "social", "somatic", "milestone"]
            category = milestone_categories[i % len(milestone_categories)]

        content = resolve_placeholders(template, i)
        content = f"{content} [Milestone ID: {i}]"

        m_valence = (
            round(rng.uniform(-0.80, -0.20), 4)
            if category == "crisis"
            else round(rng.uniform(0.40, 0.95), 4)
        )

        # Calculate diurnal time simulation factor
        t_hour = created_time.hour
        diurnal = 0.5 + 0.5 * math.sin(2 * math.pi * (t_hour - 8) / 24.0)
        importance_score = round(0.75 + 0.24 * diurnal, 4)

        corpus.append(
            {
                "content": content,
                "raw_content": content,
                "wing": "personal",
                "room": category,
                "importance": importance_score,
                "emotion": round(rng.uniform(0.60, 0.95), 4),
                "valence": m_valence,
                "certainty": round(rng.uniform(0.90, 1.00), 4),
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
    generate_corpus(85000, 12000, 3000)
