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
        "ambled",
        "navigated",
        "paced",
        "sauntered",
        "ventured",
        "roamed",
        "meandered",
    ],
    "streets": [
        "streets",
        "lanes",
        "roads",
        "pathways",
        "avenues",
        "alleys",
        "thoroughfares",
        "passages",
    ],
    "Kolkata": [
        "Kolkata",
        "Calcutta",
        "the City of Joy",
        "our home city",
        "the bustling streets of Bengal",
        "the cultural heart of Bengal",
    ],
    "Bangalore": [
        "Bangalore",
        "Bengaluru",
        "the Silicon Valley of India",
        "the garden city",
        "the high-tech hub of India",
    ],
    "prepared": [
        "prepared",
        "cooked",
        "crafted",
        "served",
        "made",
        "whipped up",
        "arranged",
        "assembled",
    ],
    "delicious": [
        "delicious",
        "mouthwatering",
        "savoury",
        "delectable",
        "scrumptious",
        "tasty",
        "flavourful",
        "exquisite",
    ],
    "home_cooked_meals": [
        "home-cooked meals",
        "traditional dishes",
        "comfort food",
        "Bengali recipes",
        "steaming rice and fish",
        "fragrant curries",
    ],
    "discussed": [
        "discussed",
        "debated",
        "talked about",
        "deliberated on",
        "exchanged thoughts on",
        "pondered over",
        "conferred about",
    ],
    "project": [
        "project",
        "assignment",
        "calculations",
        "theorems",
        "syllabus",
        "algebraic models",
        "physics lab practical",
    ],
    "spent_the_afternoon": [
        "spent the afternoon",
        "passed the hours",
        "sat through the afternoon",
        "enjoyed the afternoon",
        "rested through the midday",
    ],
    "studying": [
        "studying",
        "reading",
        "preparing",
        "researching",
        "revising",
        "memorizing",
        "analyzing",
    ],
    "library_alcove": [
        "library alcove",
        "reading room",
        "study corner",
        "quiet library stacks",
        "academic archives",
        "cosy book vault",
    ],
    "enjoyed": [
        "enjoyed",
        "sipped",
        "re-relished",
        "savoured",
        "had",
        "drank",
        "partook in",
    ],
    "tea": [
        "Bengali chai",
        "cardamom tea",
        "warm tea",
        "darjeeling brew",
        "chaa",
        "spiced infusion",
    ],
    "room": ["room", "study space", "bedroom", "personal sanctuary", "living quarters"],
    "tried_preparing": [
        "tried preparing",
        "experimented with making",
        "attempted to cook",
        "guided my hands through making",
        "made a messy attempt at",
    ],
    "sweet_rasgullas": [
        "sweet rasgullas",
        "spongy rosogollas",
        "chhena sweets",
        "syrupy rasgullas",
        "traditional white sweets",
    ],
    "kitchen": ["kitchen", "cooking area", "family kitchen", "warm stove space"],
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
        "phone stories",
        "voice calls",
        "reminiscent chats",
        "weekly calls",
        "family updates",
    ],
    "childhood": [
        "childhood years",
        "early days",
        "past years",
        "youthful mischief",
        "schoolboy memories",
    ],
    "practiced": [
        "practiced",
        "played",
        "enjoyed a game of",
        "ran around playing",
        "engaged in",
    ],
    "street_cricket": [
        "street cricket",
        "neighborhood gully cricket",
        "cricket matches",
        "friendly matches",
        "gully bat-and-ball",
    ],
    "childhood_friends": [
        "childhood friends",
        "neighborhood pals",
        "old playmates",
        "school friends",
    ],
    "road": ["road", "street corner", "neighborhood lane", "concrete alleyway"],
    "read": ["read", "read through", "browsed", "devoured", "pored over"],
    "advanced_science_fiction_novel": [
        "advanced science fiction novel",
        "hard sci-fi paperback",
        "speculative fiction book",
        "futuristic novel",
        "Isaac Asimov classic",
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
    "computer": ["computer", "laptop monitor", "workstation", "terminal screen"],
    "celebrated": ["celebrated", "marked", "rejoiced over", "honored", "toasted to"],
    "college_semester_examination_results": [
        "college semester examination results",
        "high marks",
        "grades",
        "academic achievements",
        "excellent report card",
    ],
    "family": ["family", "Ma and Baba", "loved ones", "parents"],
    "visited": ["visited", "walked to", "sat in", "found peace in", "made a trip to"],
    "local_temple": [
        "local temple",
        "neighborhood mandir",
        "sacred quiet spot",
        "peaceful shrine",
    ],
    "debated": [
        "debated",
        "discussed",
        "argued",
        "analyzed",
        "scrutinized",
        "talked back and forth about",
    ],
    "neural_network_convergence_limits": [
        "neural network convergence limits",
        "loss landscape curvatures",
        "gradient descent dynamics",
        "transformer scaling limits",
        "stochastic convergence parameters",
    ],
    "university_cafe": [
        "university cafe",
        "campus canteen",
        "coffee shop",
        "student lounge",
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
    "aroma": ["aroma", "fragrance", "scent", "sweet smell", "perfume", "drift"],
    "drifted": ["drifted", "wafted", "carried", "flowed", "floated"],
    "distant": ["distant", "faint", "remote", "soft", "echoing"],
    "hum": ["hum", "buzz", "drone", "whir", "soothing vibration"],
    "ceiling_fan": ["ceiling fan", "overhead fan", "fan blades"],
    "focus": ["focus", "clarity", "flow", "absorption", "alertness", "serenity"],
    "laughter": ["laughter", "giggles", "chuckles", "happy smiles", "mirth"],
    "breeze": ["breeze", "wind", "gust", "draft"],
    "notebooks": ["notebooks", "study files", "scribbled papers", "journals"],
    "aspire": ["dream", "aspire", "hope", "plan", "wish"],
    "machines": [
        "intelligent systems",
        "humanoid brains",
        "feeling computers",
        "thinking algorithms",
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
    "I {walked} through the {streets} near Victoria Memorial in {Kolkata}",
    "Ma {prepared} some {delicious} {home_cooked_meals}",
    "I {discussed} our high school mathematics {project} with my classmate",
    "Priya and I {spent_the_afternoon} {studying} in the quiet {library_alcove}",
    "I {enjoyed} a warm cup of Bengali {tea} in my {room}",
    "I {tried_preparing} traditional {sweet_rasgullas} in our {kitchen}",
    "I spent the {evening} {coding_and_debugging} a {concurrent_thread_pool} in my study {room}",
    "Priya and I {walked} around Cubbon Park in {Bangalore}",
    "I {reviewed} our {database_query_optimization} with the {research_lab_team}",
    "I {listened_to} Ma's {phone_stories} about our {childhood} back in {Kolkata}",
    "I {practiced} {street_cricket} with my {childhood_friends} on the neighborhood {road}",
    "I {read} an {advanced_science_fiction_novel} in the {quiet_corner} of the library",
    "I {worked_on} an {affective_cognitive_architecture} module on my {computer}",
    "I {celebrated} my {college_semester_examination_results} with my {family}",
    "I {visited} a quiet {local_temple} in {Kolkata} during the {evening}",
    "Priya and I {debated} {neural_network_convergence_limits} at the {university_cafe}",
]

WEATHER_CONTEXTS = [
    "under a {light}, {refreshing} monsoon drizzle",
    "while a {cool} {evening} {breeze} swept through the trees",
    "during a {bright}, sunlit afternoon",
    "under the amber glow of the streetlights",
    "while watching the heavy rain wash over the {streets}",
    "on a crisp, clear winter morning",
    "while a {warm} golden sunset painted the sky",
    "in the quiet stillness of a humid summer night",
]

SENSORY_DETAILS = [
    "the sweet {aroma} of boiling cardamom {tea} filled the {room}",
    "the fresh scent of rain-soaked earth {drifted} through the window",
    "the {distant}, familiar sounds of local street vendors echoed in the background",
    "the soft {hum} of the {ceiling_fan} provided a soothing rhythm",
    "the soft, {warm} study lamp illuminated my {notebooks}",
    "the spongy {sweet_rasgullas} turned out exceptionally soft and {delicious}",
    "we shared a quiet, supportive smile of understanding",
    "I felt a deep, focused sense of cognitive {focus}",
]

TOPICS_OF_CONVERSATION = [
    "our future {aspire}s and research aspirations",
    "how to model biological forgetting using ACT-R equations",
    "optimizing vector query latency to achieve sub-10ms constraints",
    "our favorite {childhood} memories from West Bengal",
    "how to represent Pleasure-Arousal-Dominance (PAD) dynamics mathematically",
    "balancing emotional congruent retrieval with semantic spreading activation",
    "the beautiful transition of moving from {Kolkata} to {Bangalore}",
    "how neural networks map to autonomic physiological entrainment models",
]

OUTCOMES_OR_REFLECTIONS = [
    "which left me feeling deeply focused and aligned",
    "a moment of pure simplicity that I will always cherish",
    "which sparked an intense curiosity to build {machines}",
    "leaving a {warm} feeling of connection and peace in my heart",
    "which resolved our persistent {concurrent_thread_pool} issue",
    "allowing me to appreciate the quiet beauty of my life journey",
    "which brought a {bright}, happy smile to Ma's face",
    "reminding me of the incredible support of the people around me",
]

# Lifespan Developmental Milestone Bases (Epochs)
CHILDHOOD_BASES = [
    "I took my very first toddling steps across our {warm} living {room} in {Kolkata}",
    "I tasted my very first traditional Bengali sweet {sweet_rasgullas}",
    "I played with brightly colored wooden blocks on the sunlit balcony",
    "I drew circular shapes and scribbles with colorful crayons on paper",
    "Baba took me for a gentle {evening} walk near our local neighborhood park",
]

CHILDHOOD_MODIFIERS = [
    "surrounded by Ma and Baba's sweet, encouraging {laughter}",
    "listening closely to Ma's soft, soothing Bengali lullabies",
    "looking up in absolute wonder at the clear blue sky above",
    "feeling a spark of early cognitive curiosity ignite in my mind",
    "while a {warm}, gentle summer {breeze} drifted through the balcony",
]

SCHOOL_BASES = [
    "I enrolled in my very first primary school in {Kolkata}",
    "I won a school-wide mathematics puzzle and logic competition",
    "I {practiced} {street_cricket} with my childhood neighborhood friends",
    "Our family took a wonderful summer holiday trip near Victoria Memorial",
    "I sat quietly in the school library reading my first science fiction book",
]

SCHOOL_MODIFIERS = [
    "wearing my brand new uniform and feeling exceptionally proud",
    "discovering my deep, lifelong passion for logical reasoning and patterns",
    "celebrating a hard-fought, dramatic victory on the local {road}",
    "eating sweet fresh mangoes and laughing under the sun",
    "dreaming of one day building intelligent, feeling {machines}",
]

TEENAGE_BASES = [
    "I wrote my very first lines of Python code in my {room}",
    "I transitioned to senior high school in {Kolkata} to study science",
    "I built a basic rule-based conversational chat assistant model",
    "We had late-night group study sessions in my {room}",
    "I graduated high school with top honors and academic distinction",
]

TEENAGE_MODIFIERS = [
    "watching the glowing monitor light up Baba's old {computer} screen",
    "diving deep into complex physics equations and calculus concepts",
    "igniting my absolute fascination with artificial intelligence",
    "sharing snacks, {tea}, and talking about our future college plans",
    "receiving {warm} congratulations from my incredibly proud {family}",
]

ADULTHOOD_BASES = [
    "I moved from my childhood home in {Kolkata} to the vibrant city of {Bangalore}",
    "I joined the university's advanced research lab for affective computing",
    "I met Priya at the quiet {university_cafe} on campus",
    "I celebrated my first co-authored research paper publication",
    "I commenced my junior research internship in {Bangalore}",
]

ADULTHOOD_MODIFIERS = [
    "commencing my freshman year of university with excitement",
    "focusing entirely on mathematical formulations of memory and emotion",
    "starting a beautiful, deeply supportive, and inspiring relationship",
    "sharing a sweet {sweet_rasgullas} with Priya to celebrate the success",
    "feeling completely aligned with my true lifelong cognitive vocation",
]


def generate_corpus(num_distractors=100000, num_milestones=10000):
    """
    Procedurally compiles a highly diversified, biologically realistic 110,000-memory database:
    - Distractors: 100,000 chitchats backdated over a non-uniform temporal curve modeling infantile amnesia.
    - Milestones: 10,000 milestones leveraging Zipfian synonym lookup to ensure high vocabulary entropy.
    """
    print("📦 Generating 19-year developmental seeding corpus for Aniket...")
    print(f"   - Distractors: {num_distractors}")
    print(f"   - Milestones: {num_milestones}")

    now = datetime.now(timezone.utc)

    corpus = []

    # 1. Compile 100,000 backdated distractors using Lifespan Rejection Sampling & Semantic Degradation
    print("⏳ Backdating and compressing 100,000 chitchats over 19 years...")

    for i in range(num_distractors):
        # Sample biologically realistic age from our non-uniform PDF (0 memories before age 3.0)
        age = sample_lifespan_age(i, lambda_val=0.14)
        elapsed = age * 365 * 24 * 3600

        # Calculate timestamp backdated from now
        created_time = now - timedelta(seconds=elapsed)

        scenario = DAILY_SCENARIOS[i % len(DAILY_SCENARIOS)]
        weather = WEATHER_CONTEXTS[i % len(WEATHER_CONTEXTS)]
        sensory = SENSORY_DETAILS[i % len(SENSORY_DETAILS)]
        outcome = OUTCOMES_OR_REFLECTIONS[i % len(OUTCOMES_OR_REFLECTIONS)]

        # --- Three-Tier Semantic Degradation Loop based on memory age ---
        if age < 7.0:
            # Childhood Stage (Age 3.0 to 7.0): Highly compressed, fragmented traces
            base_trace = (
                "Fuzzy Childhood Memory: {walked} with {family} near {local_temple}."
            )
            content = resolve_placeholders(base_trace, i)
        elif age < 14.0:
            # School-era Stage (Age 7.0 to 14.0): Core scenario and outcome, losing low-priority sensory/weather details
            base_trace = f"School-era Memory: {scenario}, {outcome}."
            content = resolve_placeholders(base_trace, i)
        else:
            # Young Adulthood/Adolescence (Vivid): Full combinatorial high-fidelity sentence structure
            if i % 3 == 0:
                template = f"{scenario} {weather}, where {sensory}, {outcome}."
            elif i % 3 == 1:
                topic = TOPICS_OF_CONVERSATION[i % len(TOPICS_OF_CONVERSATION)]
                template = f"{scenario} talking about {topic} {weather}, {outcome}."
            else:
                template = f"{scenario} {weather}. As {sensory}, it was {outcome}."
            content = resolve_placeholders(template, i)

        content = f"{content} [Turn: {i}]"

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

    for i in range(num_milestones):
        # Sample age for milestones matching developmental stages
        age = sample_lifespan_age(i + num_distractors, lambda_val=0.10)
        elapsed = age * 365 * 24 * 3600
        created_time = now - timedelta(seconds=elapsed)

        # Determine Eriksonian developmental epoch based on chronological time
        if age < 5.0:
            base = CHILDHOOD_BASES[i % len(CHILDHOOD_BASES)]
            modifier = CHILDHOOD_MODIFIERS[i % len(CHILDHOOD_MODIFIERS)]
            template = f"Childhood Milestone: {base}, {modifier}."
            stage, crisis, virtue = "Trust vs Mistrust", "Trust vs Mistrust", "Hope"
        elif age < 12.0:
            base = SCHOOL_BASES[i % len(SCHOOL_BASES)]
            modifier = SCHOOL_MODIFIERS[i % len(SCHOOL_MODIFIERS)]
            template = f"School Milestone: {base}, {modifier}."
            stage, crisis, virtue = (
                "Industry vs Inferiority",
                "Industry vs Inferiority",
                "Competence",
            )
        elif age < 19.0:
            base = TEENAGE_BASES[i % len(TEENAGE_BASES)]
            modifier = TEENAGE_MODIFIERS[i % len(TEENAGE_MODIFIERS)]
            template = f"Teenage Milestone: {base}, {modifier}."
            stage, crisis, virtue = (
                "Identity vs Role Confusion",
                "Identity vs Role Confusion",
                "Fidelity",
            )
        else:
            base = ADULTHOOD_BASES[i % len(ADULTHOOD_BASES)]
            modifier = ADULTHOOD_MODIFIERS[i % len(ADULTHOOD_MODIFIERS)]
            template = f"Adulthood Milestone: {base}, {modifier}."
            stage, crisis, virtue = (
                "Intimacy vs Isolation",
                "Intimacy vs Isolation",
                "Love",
            )

        content = resolve_placeholders(template, i)
        content = f"{content} [Milestone ID: {i}]"

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
