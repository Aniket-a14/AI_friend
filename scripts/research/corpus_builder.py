import re

# ==============================================================================
# INDIRECT RECALL QUESTIONS (Indirect mapping to avoid prompt parroting)
# ==============================================================================

RECALL_QUESTIONS = [
    {
        "question": "Can you describe how my early days in our shared workspace influenced my college research topic?",
        "entities": ["our shared workspace", "affective cognitive architectures"],
    },
    {
        "question": "Did my university project on college research help me get my first job in the testing laboratory?",
        "entities": ["affective cognitive architectures", "the testing laboratory"],
    },
    {
        "question": "How did moving to the testing laboratory affect my early days with my friend?",
        "entities": ["the testing laboratory", "my friend"],
    },
    {
        "question": "What relaxing drink do I love to share with my friend?",
        "entities": ["my friend", "chamomile brew"],
    },
    {
        "question": "Is my favorite relaxing drink a specialty of our shared workspace?",
        "entities": ["our shared workspace", "chamomile brew"],
    },
    {
        "question": "How did moving from our shared workspace to the testing laboratory shape my early career?",
        "entities": ["our shared workspace", "the testing laboratory"],
    },
    {
        "question": "Did my friend know about the research topic I worked on during college?",
        "entities": ["my friend", "affective cognitive architectures"],
    },
    {
        "question": "What is my favorite relaxing drink, and is it a local specialty of our shared workspace?",
        "entities": ["our shared workspace", "chamomile brew"],
    },
    {
        "question": "Did my university research topic inspire my early work in the testing laboratory?",
        "entities": ["affective cognitive architectures", "the testing laboratory"],
    },
    {
        "question": "If I wanted to celebrate my first job with my friend, what drink would we share?",
        "entities": ["the testing laboratory", "my friend", "chamomile brew"],
    },
    {
        "question": "How do my early days in our shared workspace compare to my college research topic?",
        "entities": ["our shared workspace", "affective cognitive architectures"],
    },
    {
        "question": "Did I live in our shared workspace before moving to start my very first job?",
        "entities": ["our shared workspace", "the testing laboratory"],
    },
    {
        "question": "How does my friend support my continued interest in building my college research system?",
        "entities": ["my friend", "affective cognitive architectures"],
    },
    {
        "question": "Why does my preferred relaxing drink always remind me of my early days in our shared workspace?",
        "entities": ["our shared workspace", "chamomile brew"],
    },
    {
        "question": "Did my first job focus on the same system I researched during my university project?",
        "entities": ["the testing laboratory", "affective cognitive architectures"],
    },
    {
        "question": "How would you describe the journey from our shared workspace to meeting my friend?",
        "entities": ["our shared workspace", "my friend"],
    },
    {
        "question": "Is my favorite drink the perfect treat to celebrate the completion of my university project?",
        "entities": ["chamomile brew", "affective cognitive architectures"],
    },
    {
        "question": "Can you summarize my transition from our shared workspace, to college research, to the testing laboratory?",
        "entities": [
            "our shared workspace",
            "affective cognitive architectures",
            "the testing laboratory",
        ],
    },
    {
        "question": "What relaxing drink from our shared workspace does my friend love to enjoy with me?",
        "entities": ["our shared workspace", "my friend", "chamomile brew"],
    },
    {
        "question": "Did working in the testing laboratory teach me more about my research topic than my college project?",
        "entities": ["the testing laboratory", "affective cognitive architectures"],
    },
    {
        "question": "How has my friend helped me reflect on my roots in our shared workspace?",
        "entities": ["my friend", "our shared workspace"],
    },
    {
        "question": "If I wanted to introduce colleagues in the testing laboratory to my favorite relaxing drink, what memories would I share?",
        "entities": [
            "the testing laboratory",
            "chamomile brew",
            "our shared workspace",
        ],
    },
    {
        "question": "Does my college project on my research topic have any connection to my friend?",
        "entities": ["affective cognitive architectures", "my friend"],
    },
    {
        "question": "Why does my preferred relaxing drink hold such a special place in my heart, and who is the person I share it with?",
        "entities": ["chamomile brew", "my friend"],
    },
    {
        "question": "How did the culture of our shared workspace prepare me for my first job in the testing laboratory?",
        "entities": ["our shared workspace", "the testing laboratory"],
    },
    {
        "question": "Did I start studying my research topic before or after I met my friend?",
        "entities": ["affective cognitive architectures", "my friend"],
    },
    {
        "question": "What is the favorite relaxing drink of the person who spent their first job in the testing laboratory?",
        "entities": ["chamomile brew", "the testing laboratory"],
    },
    {
        "question": "How does our shared workspace compare to the city of my first job?",
        "entities": ["our shared workspace", "the testing laboratory"],
    },
    {
        "question": "Would my university project have been successful without the support of my friend?",
        "entities": ["affective cognitive architectures", "my friend"],
    },
    {
        "question": "If my friend and I travel back to our shared workspace, what traditional relaxing drink should we buy first?",
        "entities": ["my friend", "our shared workspace", "chamomile brew"],
    },
    {
        "question": "Did the research team at my first job value my college expertise in my core research topic?",
        "entities": ["the testing laboratory", "affective cognitive architectures"],
    },
    {
        "question": "How did growing up in our shared workspace shape my choice to study my university project topic?",
        "entities": ["our shared workspace", "affective cognitive architectures"],
    },
    {
        "question": "Did I move directly from our shared workspace to my first job?",
        "entities": ["our shared workspace", "the testing laboratory"],
    },
    {
        "question": "How does my friend feel about the research topic that I did in university?",
        "entities": ["my friend", "affective cognitive architectures"],
    },
    {
        "question": "Why does my preferred relaxing drink from our shared workspace bring back so many nostalgic feelings?",
        "entities": ["chamomile brew", "our shared workspace"],
    },
    {
        "question": "How did my first job lay the groundwork for my career, and did my friend join me in that city?",
        "entities": ["the testing laboratory", "my friend"],
    },
    {
        "question": "Is my favorite relaxing drink also loved by my friend?",
        "entities": ["chamomile brew", "my friend"],
    },
    {
        "question": "How did my early days in our shared workspace inspire my intellectual awakening in building my college project?",
        "entities": ["our shared workspace", "affective cognitive architectures"],
    },
    {
        "question": "What would my colleagues in the testing laboratory say if I offered them a relaxing drink?",
        "entities": ["the testing laboratory", "chamomile brew"],
    },
    {
        "question": "How does my friend support my professional reflections on my first job?",
        "entities": ["my friend", "the testing laboratory"],
    },
    {
        "question": "Is my favorite relaxing drink from our shared workspace a favorite of my friend?",
        "entities": ["chamomile brew", "our shared workspace", "my friend"],
    },
    {
        "question": "Did my research in university help me transition to the testing laboratory?",
        "entities": ["affective cognitive architectures", "the testing laboratory"],
    },
    {
        "question": "What are the most vivid memories of our shared workspace that I have shared with my friend?",
        "entities": ["our shared workspace", "my friend"],
    },
    {
        "question": "Did my love for my favorite relaxing drink develop during my childhood in our shared workspace or later in the testing laboratory?",
        "entities": [
            "chamomile brew",
            "our shared workspace",
            "the testing laboratory",
        ],
    },
    {
        "question": "How did my academic focus on my research topic influence my daily routines in the testing laboratory?",
        "entities": ["affective cognitive architectures", "the testing laboratory"],
    },
    {
        "question": "What makes our shared workspace and my friend so central to my life story?",
        "entities": ["our shared workspace", "my friend"],
    },
    {
        "question": "Did I ever buy my favorite relaxing drink with my first paycheck in the testing laboratory?",
        "entities": ["chamomile brew", "the testing laboratory"],
    },
    {
        "question": "How did my university years studying my research topic lead to a career in the testing laboratory?",
        "entities": ["affective cognitive architectures", "the testing laboratory"],
    },
    {
        "question": "What relaxing drink would my friend and I drink to celebrate our memories of our shared workspace?",
        "entities": ["chamomile brew", "my friend", "our shared workspace"],
    },
    {
        "question": "Can you summarize how our shared workspace, the testing laboratory, and my friend define my journey?",
        "entities": ["our shared workspace", "the testing laboratory", "my friend"],
    },
]

# ==============================================================================
# LIFE CORPUS DEFINITIONS
# ==============================================================================

DOMAINS = [
    "computational neuroscience",
    "quantum thermodynamics",
    "behavioral economics",
    "molecular biology",
    "stellar astrophysics",
    "marine ecology",
    "organic chemistry",
    "epigenetics",
    "discrete mathematics",
    "linguistic anthropology",
    "analytical chemistry",
    "applied mechanics",
    "archaeological science",
    "artificial intelligence",
    "atmospheric physics",
    "avian biology",
    "biochemical engineering",
    "biodiversity conservation",
    "bioinformatics analysis",
    "biomechanical modeling",
    "biophysical chemistry",
    "botanical taxonomy",
    "cartographic science",
    "cellular pathology",
    "climatological modeling",
    "cognitive psychology",
    "comparative literature",
    "complex analysis",
    "computational logic",
    "condensed matter physics",
    "control systems engineering",
    "cryptographic engineering",
    "developmental economics",
    "digital signal processing",
    "dermatological research",
    "ecological modeling",
    "econometric modeling",
    "educational psychology",
    "electrical engineering",
    "electrochemistry study",
    "evolutionary developmental biology",
    "fluid dynamics analysis",
    "forensic entomology",
    "game theory analysis",
    "gene regulatory networks",
    "geomorphological mapping",
    "glacial hydrology",
    "historical musicology",
    "human-computer interaction",
    "immunological profiling",
    "industrial robotics",
    "information theory research",
    "inorganic chemistry",
    "macroeconomic modeling",
    "materials science engineering",
    "mathematical logic",
    "microbial ecology",
    "microclimatology study",
    "nanophotonics research",
    "neuroendocrinology study",
    "nuclear engineering",
    "numerical analysis",
    "oceanographic profiling",
    "optical physics",
    "organic synthesis",
    "paleoanthropological discovery",
    "parasitological research",
    "particle physics phenomenology",
    "petrological analysis",
    "pharmacokinetics modeling",
    "phonological theory",
    "photovoltaic engineering",
    "plant physiology",
    "political philosophy",
    "polymer chemistry",
    "population genetics",
    "quantum computing architecture",
    "quantum electrodynamics",
    "radiological imaging",
    "renal physiology",
    "rheumatological research",
    "seismological monitoring",
    "sociolinguistic mapping",
    "software engineering architecture",
    "solid state chemistry",
    "spectroscopic analysis",
    "statistical mechanics",
    "structural geology",
    "superconductivity research",
    "systems biology networks",
    "tectonic plate modeling",
    "theoretical cosmology",
    "thermal engineering design",
    "toxicological screening",
    "transcriptomic profiling",
    "urban planning sociology",
    "virological research",
    "volcanological monitoring",
    "wildlife epidemiology",
    "zoological classification",
]

LIFE_FACTORS = [
    "nutritional intake",
    "circadian rhythm stability",
    "physical aerobic activity",
    "social connection depth",
    "financial budget management",
    "commute duration",
    "ergonomic workspace comfort",
    "daily caffeine intake",
    "sleep quality",
    "stress management habits",
    "hydration tracking",
    "mindfulness meditation practice",
    "family caregiving duties",
    "personal hobby progress",
    "digital screen exposure",
    "living space hygiene",
    "community service involvement",
    "intellectual stimulation balance",
    "indoor air quality",
    "outdoor green space exposure",
    "vocational alignment",
    "creative writing time",
    "musical practice duration",
    "recreational reading volume",
    "financial savings rate",
    "meal prep consistency",
    "social media consumption",
    "time spent outdoors",
    "household chore efficiency",
    "active learning hours",
    "verbal interaction quality",
    "physical posture habits",
    "sleep latency duration",
    "noise pollution exposure",
    "vitamin D synthesis",
    "friendship network engagement",
    "romantic relationship harmony",
    "career trajectory planning",
    "hobbies exploration activity",
    "micro-break frequency",
    "task prioritization methods",
    "workload distribution safety",
    "home organization standards",
    "cultural activity participation",
    "spiritual practice alignment",
    "gastrointestinal comfort level",
    "muscle tone maintenance",
    "cardiovascular endurance exercises",
    "stretching routine frequency",
    "ambient light exposure",
    "professional networking consistency",
    "volunteering hours",
    "gardening activity duration",
    "pet ownership interaction",
    "cooking experimentation frequency",
    "laundry cycle organization",
    "budget surplus utilization",
    "investment portfolio monitoring",
    "debt reduction progress",
    "emergency fund stability",
    "academic lecture attendance",
    "mentorship session frequency",
    "journaling consistency",
    "public transport usage",
    "bicycle commuting frequency",
    "footwear comfort rating",
    "dental hygiene rigor",
    "skin care consistency",
    "water temperature preference",
    "thermostat setting preference",
    "neighbor interaction frequency",
    "local shopping frequency",
    "online subscription auditing",
    "desk clutter organization",
    "clothing closet simplification",
    "tool repair skill improvement",
    "DIY project completion",
    "leisure travel frequency",
    "nature hike duration",
    "photography exploration activity",
    "museum visit frequency",
    "theater show attendance",
    "board game night hosting",
    "family phone call frequency",
    "letter writing practice",
    "scrapbooking activity duration",
    "puzzle solving consistency",
    "language learning streak",
    "medication adherence accuracy",
    "allergy symptom severity",
    "cough and cold frequency",
    "joint mobility levels",
    "back muscle flexibility",
    "eye strain occurrence",
    "headache recovery duration",
    "dental checkup regularity",
    "annual physical screening",
    "preventative medicine practices",
    "health insurance coverage",
    "sleep schedule consistency",
]

CONDITIONS = [
    "mild cognitive fatigue",
    "acute creative flow",
    "persistent performance anxiety",
    "deep emotional calm",
    "heightened sensory sensitivity",
    "chronic mild dehydration",
    "ambient noise distraction",
    "optimal cognitive readiness",
    "slight physical restlessness",
    "subtle digital fatigue",
    "mild depressive mood",
    "elevated social curiosity",
    "profound physical exhaustion",
    "acute focus hyperstate",
    "general life satisfaction",
    "existential reflection mood",
    "seasonal affective shift",
    "acute caffeine alert state",
    "moderate social exhaustion",
    "general ambient optimism",
    "mild somatic stress",
    "intellectual overstimulation",
    "chronic time pressure",
    "calm environmental serenity",
    "elevated competitive drive",
    "subtle emotional vulnerability",
    "intense problem-solving fatigue",
    "deep artistic inspiration",
    "mild background apprehension",
    "optimal task engagement",
    "transient mental block",
    "vibrant physical vitality",
    "mild situational frustration",
    "profound scientific curiosity",
    "mild sensory overload",
    "peaceful domestic tranquility",
    "subtle career dissatisfaction",
    "acute project urgency stress",
    "elevated altruistic motivation",
    "mild environmental discomfort",
    "moderate muscle soreness",
    "heightened intuitive awareness",
    "slight social awkwardness",
    "intense logical concentration",
    "warm empathetic connection",
    "subtle nostalgic longing",
    "mild decision fatigue",
    "acute multitasking overload",
    "profound intellectual humility",
    "slight seasonal lethargy",
    "elevated aesthetic appreciation",
    "mild digestive discomfort",
    "ambient temperature discomfort",
    "acute mathematical clarity",
    "subtle romantic anxiety",
    "general financial confidence",
    "mild somatic tension",
    "elevated creative confidence",
    "deep spiritual alignment",
    "subtle family harmony",
    "intense research motivation",
    "mild routine boredom",
    "optimal physical balance",
    "slight cognitive hesitation",
    "acute emotional stability",
    "profound existential peace",
    "subtle social integration",
    "mild work-life imbalance",
    "elevated collaboration enthusiasm",
    "chronic sleep deprivation state",
    "ambient light deprivation",
    "acute analytical sharp state",
    "subtle creative block",
    "general health confidence",
    "mild academic pressure",
    "elevated competitive anxiety",
    "deep professional fulfillment",
    "subtle domestic friction",
    "intense learning desire",
    "mild attention deficit state",
    "optimal recovery sleep quality",
    "slight physical stiffness",
    "acute strategic mindset",
    "profound emotional resilience",
    "subtle environmental alignment",
    "mild professional burnout",
    "elevated teaching enthusiasm",
    "deep philosophical wonder",
    "subtle relational harmony",
    "intense software optimization focus",
    "mild communication fatigue",
    "optimal physiological state",
    "slight decision hesitation",
    "acute cognitive agility",
    "profound moral clarity",
    "subtle personal growth",
    "mild social detachment",
    "elevated community trust",
    "deep intellectual curiosity",
    "subtle emotional maturity",
]

PHASES_OF_LIFE = [
    # Infancy, Childhood, Play, School Age additions
    "my infancy at age 1",
    "my early childhood toddler years at age 2",
    "my early childhood at age 3",
    "my preschool play age at age 4",
    "my kindergarten years at age 5",
    "my early school age at age 7",
    "my elementary school years at age 9",
    "my pre-teen school age at age 11",
    # Adolescence
    "my early adolescence at age 15",
    "my developing years at age 16",
    "my high school transition at age 17",
    "my senior high school experience at age 18",
    "my freshman year of university at age 19",
    # Young Adulthood
    "my sophomore college year at age 20",
    "my junior college research phase at age 21",
    "my senior college graduation milestone at age 22",
    "my early twenties job hunt at age 23",
    "my first entry-level position at age 24",
    "my initial professional growth at age 25",
    # Adulthood
    "my career exploration phase at age 26",
    "my budding professional expertise at age 27",
    "my mid-twenties networking phase at age 28",
    "my early career stabilization at age 29",
    "my entrance into my thirties at age 30",
    "my early thirties skill expansion at age 31",
    "my professional consolidation phase at age 32",
    "my mid-career trajectory shift at age 33",
    "my early thirties domestic settling at age 34",
    "my mid-thirties personal milestones at age 35",
    "my career path diversification at age 36",
    "my professional peer mentoring at age 37",
    "my mid-thirties leadership trials at age 38",
    "my organizational responsibility growth at age 39",
    "my entry into my forties at age 40",
    "my early forties lifestyle calibration at age 41",
    "my mid-career advisory roles at age 42",
    "my professional legacy planning at age 43",
    "my early forties community engagement at age 44",
    "my mid-forties family transitions at age 45",
    "my career re-evaluation phase at age 46",
    "my intellectual horizon broadening at age 47",
    "my senior leadership tenure at age 48",
    "my late-forties career reflection at age 49",
    "my entrance into my fifties at age 50",
    "my senior industry expert role at age 51",
    "my mid-fifties consulting phase at age 52",
    "my professional writing endeavors at age 53",
    "my late-fifties mentorship focus at age 54",
    "my retirement planning transitions at age 55",
    "my pre-retirement career wind-down at age 56",
    "my early retirement explorations at age 57",
    "my late-fifties spiritual awakening at age 58",
    "my serene life reflections at age 59",
    "my entrance into my sixties at age 60",
    "my early sixties leisure travels at age 61",
    "my retirement hobbies immersion at age 62",
    "my mid-sixties voluntary mentoring at age 63",
    "my community legacy contribution at age 64",
    # Old Age
    "my peaceful senior lifestyle at age 65",
    "my late-sixties local volunteering at age 66",
    "my home gardening explorations at age 67",
    "my childhood nostalgia reflections at age 68",
    "my family history documentation at age 69",
    "my entrance into my seventies at age 70",
    "my early seventies contemplation phase at age 71",
    "my quiet elder wisdom advisory roles at age 72",
    "my late-life journal writing at age 73",
    "my reflective walks in local parks at age 74",
    "my serene domestic retirement at age 75",
    "my sharing of family heirlooms at age 76",
    "my light physical health routines at age 77",
    "my humorous storytelling to youngsters at age 78",
    "my deep quiet elder contentment at age 79",
    "my entrance into my eighties at age 80",
    "my early eighties family gatherings at age 81",
    "my quiet afternoon tea routines at age 82",
    "my complete inner peace milestone at age 83",
    "my deep octogenarian reflection at age 84",
    # Elderhood
    "my elderhood reflections at age 86",
    "my quiet contemplation at age 88",
    "my late elderhood years at age 92",
    "my centenarian milestone at age 100",
    # Extra epochs and phases to preserve all original entities
    "my late-teens hobby specialization at age 17",
    "my first college internship trials at age 20",
    "my university thesis defense week at age 22",
    "my initial post-college residency at age 23",
    "my professional license certification at age 25",
    "my public speaking debut at age 27",
    "my promotion to team lead duties at age 29",
    "my home relocation experience at age 31",
    "my first international business trip at age 33",
    "my mid-career research sabbatical at age 35",
    "my keynote conference presentation at age 38",
    "my initial venture capital exploration at age 41",
    "my executive board appointment at age 44",
    "my scientific patent filing year at age 46",
    "my corporate transformation project at age 49",
    "my industry textbook publication at age 52",
    "my lifetime contribution award week at age 55",
    "my university guest lecture series at age 58",
    "my local community center founding at age 61",
    "my writing of a historical novel at age 64",
    "my family ancestral tree completion at age 67",
    "my local history archives archiving at age 70",
    "my lifetime achievement dinner speech at age 73",
    "my silver anniversary retirement party at age 75",
    "my local municipal honor ceremony at age 77",
    "my writing of poetry and essays at age 80",
    "my golden wedding anniversary celebration at age 82",
    "my community library dedication day at age 83",
    "my historical legacy preservation week at age 84",
    "my peaceful sunset years milestone at age 84",
]

# ==============================================================================
# ADDITIONAL SEMANTIC DIMENSIONS FOR 40-DIMENSIONAL COGNITIVE STATE SPACE
# ==============================================================================

ENVIRONMENTS = [
    "a cozy wood-paneled study",
    "a sunlit botanical garden",
    "a crowded university cafe",
    "a quiet library alcove",
    "a spacious high-ceilinged workshop",
    "a modern server room with cooling fans",
    "a peaceful lakeside cabin",
    "a high-altitude mountain research station",
    "a bustling city square",
    "a quiet rooftop terrace",
    "a glass-walled laboratory",
    "a high-speed train compartment",
]
SENSORY_INPUTS = [
    "the scent of rain-dampened earth",
    "the aroma of dark roasted espresso",
    "the rhythmic clack of mechanical keyboard keys",
    "the bright neon glow of streetlights",
    "the soft warmth of a fireplace",
    "the low hum of distant city traffic",
    "the refreshing taste of peppermint tea",
    "the crisp clean scent of pine needles",
    "the crisp rustle of autumn leaves",
    "the distant chime of church bells",
    "the faint smell of ozone",
    "the soothing warmth of sunlight on skin",
]
WEATHER = [
    "overcast skies",
    "a crisp autumn breeze",
    "heavy monsoon rain",
    "humid summer heat",
    "gentle winter snowfall",
    "bright spring sunshine",
    "dense morning fog",
    "a warm tropical evening",
    "a raging thunderstorm",
    "a quiet overcast afternoon",
    "a biting winter wind",
    "a humid tropical night",
]
TIME_OF_DAY = [
    "the early dawn light",
    "the mid-afternoon peak hours",
    "the golden sunset hour",
    "the quiet midnight silence",
    "the twilight transition",
    "late-evening shadows",
    "mid-morning clarity",
    "a sleepless pre-dawn",
    "the hazy mid-morning hours",
    "the late-night quietness",
    "the post-lunch slump",
    "the brisk pre-dawn chill",
]
COGNITIVE_MODES = [
    "deep algorithmic deduction",
    "light recreational reading",
    "passive observational learning",
    "creative brainstorming",
    "meticulous code debugging",
    "philosophical meta-reflection",
    "strategic pattern mapping",
    "spontaneous intuitive insights",
    "intuitive pattern mapping",
    "focused document synthesis",
    "intense mathematical modeling",
    "creative outline drafting",
]
PHYSICAL_STATUS = [
    "peak physical vitality",
    "slight joint stiffness",
    "mild eye strain",
    "abundant neural stamina",
    "relaxed bodily ease",
    "minor muscular tension",
    "perfect cardiovascular balance",
    "recovering physical strength",
    "mild physical exhaustion",
    "restless mental alertness",
    "deep physical relaxation",
    "heightened sensory focus",
]
SOCIAL_SETTINGS = [
    "complete solitary isolation",
    "an intimate one-on-one dialogue",
    "a high-pressure team meeting",
    "a crowded public marketplace",
    "a quiet scholarly seminar",
    "a festive family gathering",
    "a professional networking reception",
    "a casual coffee with a colleague",
    "a lively group discussion",
    "a quiet one-on-one meeting",
    "a busy networking event",
    "a solitary park bench",
]
PRIMARY_ACTIVITIES = [
    "writing deep technical documentation",
    "analyzing complex data graphs",
    "refactoring memory store systems",
    "designing neural network layers",
    "reading academic research papers",
    "sketching hardware component layouts",
    "solving discrete math equations",
    "validating local database indices",
    "writing system architecture docs",
    "sketching UI wireframes",
    "optimizing database indices",
    "reviewing mathematical proofs",
]
FINANCIAL_CONTEXTS = [
    "absolute budget security",
    "conscious resource optimization",
    "monitoring market portfolios",
    "planning long-term investments",
    "reviewing monthly budget constraints",
    "allocating research capital",
    "securing project grants",
    "planning family inheritance legacy",
    "strict expense budgeting",
    "long-term investment planning",
    "checking minor receipts",
    "optimizing server costs",
]
RELATIONSHIP_TUNINGS = [
    "profound interpersonal harmony",
    "warm family conversations",
    "supportive mentor feedback",
    "deep collaboration alignment",
    "peaceful domestic quietude",
    "meaningful peer recognition",
    "building new friendship networks",
    "nurturing close personal ties",
    "deep empathetic alignment",
    "friendly intellectual debate",
    "shared quiet understanding",
    "collaborative problem solving",
]
DIETARY_METABOLISM = [
    "post-prandial satisfaction",
    "a sharp caffeine-induced alert state",
    "slight dehydration signals",
    "perfectly balanced glucose levels",
    "light nutrient replenishment",
    "a clean fasted state",
    "the warmth of an herbal beverage",
    "steady metabolic energy",
    "a high-protein meal",
    "a light fruit snack",
    "a steaming bowl of noodles",
    "a refreshing cold drink",
]
ERGONOMIC_POSTURES = [
    "upright sitting in an ergonomic chair",
    "active standing desk alignment",
    "reclined armchair posture",
    "meticulous upright research posture",
    "relaxed cushion support",
    "perfect screen-level gaze",
    "supported spinal extension",
    "comfortable forearm placement",
    "sitting at a standing desk",
    "reclined in a mesh chair",
    "pacing slowly in a circle",
    "leaning against a whiteboard",
]
VOCATIONAL_DRIVES = [
    "intense research curiosity",
    "a strong legacy creation drive",
    "perfect vocational alignment",
    "solving real-world human challenges",
    "seeking structural perfection",
    "optimizing modular system efficiency",
    "pioneering novel cognitive pipelines",
    "mentoring future scientists",
    "architecting local sovereignty",
    "optimizing latency boundaries",
    "expanding cognitive capacities",
    "perfecting user interfaces",
]
CREATIVE_OUTLETS = [
    "writing philosophical essays",
    "sketching architectural concepts",
    "composing atmospheric music",
    "journaling daily cognitive leaps",
    "crafting intricate physical models",
    "programming beautiful user interfaces",
    "photographing natural light patterns",
    "designing interactive systems",
    "writing technical blogs",
    "sketching architectural diagrams",
    "recording voice modulations",
    "journaling system designs",
]
SPIRITUAL_ATTUNEMENTS = [
    "deep meditative presence",
    "profound existential peace",
    "cosmic philosophical wonder",
    "quiet personal mindfulness",
    "holistic natural alignment",
    "harmonious inner silence",
    "intellectual humility exploration",
    "contemplative analytical calm",
    "alignment with truthfulness",
    "respect for local sovereignty",
    "intellectual humility",
    "pursuit of mathematical beauty",
]
STRESS_METRICS = [
    "absolute tranquil calm",
    "low-grade background urgency",
    "acute deadline focus",
    "steady situational confidence",
    "patient methodical progress",
    "a structured challenge response",
    "relaxed mental pacing",
    "a mindful stress-release state",
    "minor CPU latency pressure",
    "tight release timeline stress",
    "complex integration debugging anxiety",
    "calm baseline focus",
]
MOTIVATION_LEVELS = [
    "high dopamine-driven reward seeking",
    "steady task-oriented execution",
    "post-milestone relaxation",
    "eager anticipation of testing results",
    "curious exploratory motivation",
    "focused problem-solving energy",
    "deep intrinsic satisfaction",
    "enthusiastic collaborative drive",
    "intense creative flow",
    "persistent analytical drive",
    "steady routine execution",
    "focused curiosity-driven urge",
]
LEISURE_PURSUITS = [
    "playing complex strategy board games",
    "gardening in a backyard plot",
    "reading historical biography novels",
    "restoring old mechanical tools",
    "solving challenging crossword puzzles",
    "cooking elaborate traditional dishes",
    "walking through local historic neighborhoods",
    "building custom desktop rigs",
    "reading speculative fiction",
    "taking photos of nature",
    "playing chess online",
    "brewing artisanal coffee",
]
MOBILITY_MODES = [
    "walking slowly along a path",
    "riding a commuter bicycle",
    "sitting on a public transport bus",
    "standing on a moving train",
    "relaxing in a stationary vehicle",
    "climbing a gentle hillside",
    "navigating a busy urban sidewalk",
    "resting in a quiet room",
    "walking briskly",
    "riding a bicycle",
    "sitting stationary",
    "pacing slowly",
]
CLOTHING_COMFORTS = [
    "soft breathable cotton garments",
    "a cozy heavy wool sweater",
    "crisp formal research attire",
    "relaxed casual home wear",
    "a warm weather-resistant jacket",
    "perfectly broken-in leather shoes",
    "light active athletic wear",
    "layered comfortable clothing",
    "a loose cotton shirt",
    "a comfortable warm hoodie",
    "light athletic wear",
    "a simple casual jacket",
]
MEMORY_TRIGGERS = [
    "glancing at an old faded photograph",
    "hearing a nostalgic melody",
    "finding a handwritten note",
    "opening a vintage textbook",
    "catching the aroma of childhood cooking",
    "revisiting a familiar landscape",
    "encountering a historical artifact",
    "recalling a vivid past dream",
    "a sudden keyword match",
    "a familiar sensory smell",
    "an associated name mention",
    "a specific time-of-day query",
]
PACING_RHYTHMS = [
    "a meticulous slow pace",
    "a rapid focused sprint",
    "a natural comfortable flow",
    "a deliberate step-by-step progress",
    "an intense uninterrupted focus session",
    "a patient observational stance",
    "a highly flexible dynamic pace",
    "a structured routine schedule",
    "a slow contemplative crawl",
    "a rapid flow-state sprint",
    "a steady rhythmic stride",
    "an irregular experimental pace",
]
ETHICAL_STANDS = [
    "reflecting on societal contribution",
    "ensuring cognitive safety boundaries",
    "prioritizing open-source access",
    "advocating for human-centric design",
    "considering global environmental footprints",
    "pursuing honest academic rigor",
    "supporting collaborative community growth",
    "defending scientific integrity",
    "protecting user sovereignty",
    "ensuring absolute transparency",
    "demanding rigorous validation",
    "supporting local execution",
]
HYDRATION_LEVELS = [
    "perfectly hydrated with pure water",
    "sipping warm organic green tea",
    "enjoying a cold refreshing beverage",
    "rehydrating post-workout",
    "savoring a warm spiced chai",
    "drinking chilled mineral water",
    "sipping hot chamomile tea",
    "balanced fluid homeostasis",
    "a full glass of cold water",
    "a warm spiced chai",
    "a fresh coconut water",
    "a cup of green tea",
]
TEMPERATURE_COMFORTS = [
    "a mild balanced indoor climate",
    "a cool refreshing air-conditioned room",
    "cozy radial hearth warmth",
    "a fresh breezy outdoor current",
    "comfortably warm summer evening air",
    "a crisp insulated winter shelter",
    "a shaded cool retreat",
    "a sun-warmed workspace spot",
    "a cool air-conditioned draft",
    "the warm afternoon sun",
    "a cozy heated room",
    "the brisk evening air",
]
ACOUSTIC_SCAPES = [
    "complete absolute silence",
    "soft classical ambient piano",
    "a low-frequency pink noise background",
    "distant birds singing outside",
    "the gentle rustle of leaves",
    "a quiet muffled office hum",
    "a gentle rhythmic ticking clock",
    "soft acoustic guitar frequencies",
    "the steady hum of server fans",
    "the quiet rustle of paper",
    "soft ambient music",
    "the distant chatter of a cafe",
]
VISUAL_HORIZONS = [
    "a wide open green landscape",
    "dual high-resolution monitor screens",
    "detailed circuit blueprint diagrams",
    "a bookshelf packed with scientific texts",
    "a clean minimalist desk workspace",
    "an expansive window view of the sky",
    "a vibrant chalkboard covered in math",
    "a warm softlylit room interior",
    "a monitor filled with code",
    "a window looking over trees",
    "a whiteboard full of equations",
    "a quiet sunlit room",
]
METABOLIC_FATIGUE = [
    "unlimited physical stamina",
    "needing a structured micro-break",
    "a state of perfect recovery sleep",
    "light physical replenishment",
    "rested and fully recharged",
    "steady muscle recovery",
    "balanced neural resource allocation",
    "optimizing metabolic efficiency",
    "light cognitive tiredness",
    "fresh morning energy",
    "post-lunch drowsiness",
    "rested mental clarity",
]
SELF_ESTEEMS = [
    "high academic confidence",
    "profound professional humility",
    "quiet self-assured trust",
    "proud of creative milestones",
    "eager for peer feedback",
    "objective self-assessment focus",
    "grounded personal resilience",
    "a mindset of continuous growth",
    "confidence in architecture",
    "academic pride",
    "humble curiosity",
    "analytical certainty",
]
TIMELINE_EPOCHS = [
    "my early formative childhood",
    "my early twenties transition",
    "my senior research specialist era",
    "my initial professional launch years",
    "my mid-career consolidation phase",
    "my late-stage reflective years",
    "my post-university expansion period",
    "my collaborative group project tenure",
    "my late high school days",
    "my early coding years",
    "my university research era",
    "my internship transition",
]
PRIMARY_PARTNERS = [
    "a trusted senior research mentor",
    "an eager junior university peer",
    "a brilliant software engineer colleague",
    "a supportive childhood friend",
    "an expert external patent examiner",
    "a collaborative database administrator",
    "a diverse group of global researchers",
    "a patient academic supervisor",
    "a trusted research colleague",
    "a senior lab advisor",
    "an old school classmate",
    "a quiet study partner",
]
GOAL_HORIZONS = [
    "an immediate short-term daily goal",
    "a quarterly project deadline milestone",
    "a multi-year career path target",
    "a lifelong legacy contribution",
    "a weekly sprint objective",
    "an annual system audit milestone",
    "a temporary exploratory target",
    "a solid operational benchmark target",
    "sub-10ms latency scaling",
    "robust multi-agent consensus",
    "perfect affective alignment",
    "sovereign local deployment",
]
SOMATIC_COMFORTS = [
    "fully relaxed neck and shoulders",
    "flexible and stretched back muscles",
    "loose warm hand joints",
    "perfect spinal column support",
    "stamina-filled dynamic posture",
    "perfectly comfortable seated base",
    "light refreshed physical state",
    "relaxed eye muscles",
    "perfect physical comfort",
    "slight eye strain",
    "cozy warm hands",
    "cool fresh breathing",
]
INFO_SOURCES = [
    "peer-reviewed academic journal papers",
    "dense technical documentation manuals",
    "curated database resource catalogs",
    "collaborative wiki articles",
    "historical patent office archives",
    "open-source software repositories",
    "direct physical sensor telemetry",
    "comprehensive textbook chapters",
    "an academic journal paper",
    "a system log trace",
    "a git diff history",
    "a design specification doc",
]
CLUTTER_LEVELS = [
    "a perfectly pristine clean desk",
    "a minimalist organized workspace",
    "a few neatly stacked notebooks",
    "a clean table with a single device",
    "a highly functional workspace layout",
    "a structured reference material stack",
    "a spotless laboratory workbench",
    "an uncluttered digital directory",
    "a clean organized desk",
    "a chaotic whiteboard",
    "multiple open tabs",
    "a single active window",
]
NATURAL_EXPOSURES = [
    "abundant desk plant foliage",
    "a large window showing green trees",
    "frequent short walks in a local park",
    "fresh outdoor mountain air",
    "the grounding presence of nature",
    "a nearby office botanical terrace",
    "natural ambient lighting",
    "views of natural water features",
    "a potted plant on the desk",
    "sunlight filtering through leaves",
    "a view of the sky",
    "the sound of rain outside",
]

ERIKSONIAN_MESH_SCAFFOLD = {
    "Infancy (0-1)": {
        "stage_name": "Infancy (0-1)",
        "crisis": "Trust vs. Mistrust",
        "virtue": "Hope",
        "relations": "Maternal person",
        "relation_circles": "Maternal person",
        "modality": "To get, to give in return",
    },
    "Early Childhood (1-3)": {
        "stage_name": "Early Childhood (1-3)",
        "crisis": "Autonomy vs. Shame and Doubt",
        "virtue": "Will",
        "relations": "Parental persons",
        "relation_circles": "Parental persons",
        "modality": "To hold on, to let go",
    },
    "Play Age (3-6)": {
        "stage_name": "Play Age (3-6)",
        "crisis": "Initiative vs. Guilt",
        "virtue": "Purpose",
        "relations": "Basic family",
        "relation_circles": "Basic family",
        "modality": "To go after, to make",
    },
    "School Age (6-12)": {
        "stage_name": "School Age (6-12)",
        "crisis": "Industry vs. Inferiority",
        "virtue": "Competence",
        "relations": "Neighborhood and school",
        "relation_circles": "Neighborhood and school",
        "modality": "To make things, to make things together",
    },
    "Adolescence (12-19)": {
        "stage_name": "Adolescence (12-19)",
        "crisis": "Identity vs. Role Confusion",
        "virtue": "Fidelity",
        "relations": "Peer groups and outgroups",
        "relation_circles": "Peer groups and outgroups",
        "modality": "To define and share self",
    },
    "Young Adulthood (20-25)": {
        "stage_name": "Young Adulthood (20-25)",
        "crisis": "Intimacy vs. Isolation",
        "virtue": "Love",
        "relations": "Partners and friends",
        "relation_circles": "Partners and friends",
        "modality": "To lose and find oneself in another",
    },
    "Adulthood (26-64)": {
        "stage_name": "Adulthood (26-64)",
        "crisis": "Generativity vs. Stagnation",
        "virtue": "Care",
        "relations": "Divided labor and shared household",
        "relation_circles": "Divided labor and shared household",
        "modality": "To make be, to take care of",
    },
    "Old Age (65-85)": {
        "stage_name": "Old Age (65-85)",
        "crisis": "Integrity vs. Despair",
        "virtue": "Wisdom",
        "relations": "Mankind / My kind",
        "relation_circles": "Mankind / My kind",
        "modality": "To be, through having been, to face not being",
    },
    "Elderhood (85+)": {
        "stage_name": "Elderhood (85+)",
        "crisis": "Despair vs. Gerotranscendence",
        "virtue": "Hope / Wisdom / Faith",
        "relations": "All creation / All humankind",
        "relation_circles": "All creation / All humankind",
        "modality": "To let go, to transcend",
    },
}

ERIKSONIAN_MESH_Scaffold = ERIKSONIAN_MESH_SCAFFOLD


def get_eriksonian_stage_for_phase(phase_str: str) -> str:
    match = re.search(r"age (\d+)", phase_str)
    if match:
        age = int(match.group(1))
        if age <= 1:
            return "Infancy (0-1)"
        elif age <= 3:
            return "Early Childhood (1-3)"
        elif age <= 6:
            return "Play Age (3-6)"
        elif age <= 12:
            return "School Age (6-12)"
        elif age <= 19:
            return "Adolescence (12-19)"
        elif age <= 25:
            return "Young Adulthood (20-25)"
        elif age <= 64:
            return "Adulthood (26-64)"
        elif age <= 84:
            return "Old Age (65-85)"
        else:
            return "Elderhood (85+)"
    if "adolescence" in phase_str or "teen" in phase_str:
        return "Adolescence (12-19)"
    if "college" in phase_str or "twenties" in phase_str:
        return "Young Adulthood (20-25)"
    if (
        "retirement" in phase_str
        or "sixties" in phase_str
        or "seventies" in phase_str
        or "elder" in phase_str
        or "octogenarian" in phase_str
    ):
        return "Old Age (65-85)"
    return "Adulthood (26-64)"


STAGE_COHERENT_LEAVES = {
    "Infancy (0-1)": {
        "primary_partner": ["a supportive childhood friend"],
        "cognitive_mode": [
            "passive observational learning",
            "spontaneous intuitive insights",
        ],
        "financial_context": ["absolute budget security"],
        "vocational_drive": ["solving real-world human challenges"],
        "creative_outlet": ["journaling daily cognitive leaps"],
        "primary_activity": ["reading academic research papers"],
        "leisure_pursuit": ["walking through local historic neighborhoods"],
        "social_setting": ["complete solitary isolation", "a festive family gathering"],
        "domain": ["botanical taxonomy", "marine ecology", "avian biology"],
        "timeline_epoch": ["my early formative childhood"],
    },
    "Early Childhood (1-3)": {
        "primary_partner": ["a supportive childhood friend"],
        "cognitive_mode": [
            "passive observational learning",
            "spontaneous intuitive insights",
            "creative brainstorming",
        ],
        "financial_context": ["absolute budget security"],
        "vocational_drive": ["solving real-world human challenges"],
        "creative_outlet": [
            "journaling daily cognitive leaps",
            "crafting intricate physical models",
        ],
        "primary_activity": ["reading academic research papers"],
        "leisure_pursuit": [
            "walking through local historic neighborhoods",
            "gardening in a backyard plot",
        ],
        "social_setting": ["complete solitary isolation", "a festive family gathering"],
        "domain": ["botanical taxonomy", "marine ecology", "avian biology"],
        "timeline_epoch": ["my early formative childhood"],
    },
    "Play Age (3-6)": {
        "primary_partner": ["a supportive childhood friend"],
        "cognitive_mode": [
            "creative brainstorming",
            "spontaneous intuitive insights",
            "passive observational learning",
        ],
        "financial_context": ["absolute budget security"],
        "vocational_drive": ["solving real-world human challenges"],
        "creative_outlet": [
            "sketching architectural concepts",
            "composing atmospheric music",
            "crafting intricate physical models",
        ],
        "primary_activity": ["sketching hardware component layouts"],
        "leisure_pursuit": [
            "playing complex strategy board games",
            "gardening in a backyard plot",
            "cooking elaborate traditional dishes",
        ],
        "social_setting": [
            "complete solitary isolation",
            "a festive family gathering",
            "a crowded public marketplace",
        ],
        "domain": [
            "botanical taxonomy",
            "marine ecology",
            "avian biology",
            "biodiversity conservation",
        ],
        "timeline_epoch": ["my early formative childhood"],
    },
    "School Age (6-12)": {
        "primary_partner": [
            "a supportive childhood friend",
            "an eager junior university peer",
        ],
        "cognitive_mode": [
            "light recreational reading",
            "passive observational learning",
            "deep algorithmic deduction",
            "creative brainstorming",
            "spontaneous intuitive insights",
        ],
        "financial_context": [
            "absolute budget security",
            "conscious resource optimization",
        ],
        "vocational_drive": [
            "solving real-world human challenges",
            "seeking structural perfection",
        ],
        "creative_outlet": [
            "crafting intricate physical models",
            "programming beautiful user interfaces",
            "sketching architectural concepts",
        ],
        "primary_activity": [
            "solving discrete math equations",
            "reading academic research papers",
        ],
        "leisure_pursuit": [
            "playing complex strategy board games",
            "solving challenging crossword puzzles",
            "reading historical biography novels",
        ],
        "social_setting": [
            "a festive family gathering",
            "a quiet scholarly seminar",
            "a crowded public marketplace",
        ],
        "domain": [
            "botanical taxonomy",
            "marine ecology",
            "avian biology",
            "biodiversity conservation",
            "wildlife epidemiology",
        ],
        "timeline_epoch": ["my early formative childhood"],
    },
    "Adolescence (12-19)": {
        "primary_partner": [
            "a supportive childhood friend",
            "an eager junior university peer",
        ],
        "cognitive_mode": [
            "light recreational reading",
            "creative brainstorming",
            "spontaneous intuitive insights",
            "deep algorithmic deduction",
            "philosophical meta-reflection",
        ],
        "financial_context": [
            "conscious resource optimization",
            "reviewing monthly budget constraints",
            "absolute budget security",
        ],
        "vocational_drive": [
            "intense research curiosity",
            "solving real-world human challenges",
            "seeking structural perfection",
        ],
        "creative_outlet": [
            "composing atmospheric music",
            "journaling daily cognitive leaps",
            "programming beautiful user interfaces",
            "writing philosophical essays",
        ],
        "primary_activity": [
            "solving discrete math equations",
            "reading academic research papers",
            "designing neural network layers",
        ],
        "leisure_pursuit": [
            "playing complex strategy board games",
            "solving challenging crossword puzzles",
            "reading historical biography novels",
            "building custom desktop rigs",
        ],
        "social_setting": [
            "a casual coffee with a colleague",
            "an intimate one-on-one dialogue",
            "a crowded public marketplace",
            "a festive family gathering",
        ],
        "timeline_epoch": [
            "my early formative childhood",
            "my early twenties transition",
        ],
    },
    "Old Age (65-85)": {
        "primary_partner": [
            "a supportive childhood friend",
            "a diverse group of global researchers",
            "a patient academic supervisor",
        ],
        "cognitive_mode": [
            "philosophical meta-reflection",
            "spontaneous intuitive insights",
            "light recreational reading",
            "passive observational learning",
        ],
        "financial_context": [
            "planning family inheritance legacy",
            "absolute budget security",
            "reviewing monthly budget constraints",
        ],
        "vocational_drive": [
            "mentoring future scientists",
            "a strong legacy creation drive",
            "solving real-world human challenges",
        ],
        "creative_outlet": [
            "writing philosophical essays",
            "journaling daily cognitive leaps",
            "photographing natural light patterns",
            "sketching architectural concepts",
        ],
        "primary_activity": [
            "reading academic research papers",
            "analyzing complex data graphs",
            "writing deep technical documentation",
        ],
        "leisure_pursuit": [
            "gardening in a backyard plot",
            "reading historical biography novels",
            "solving challenging crossword puzzles",
            "walking through local historic neighborhoods",
        ],
        "social_setting": [
            "complete solitary isolation",
            "an intimate one-on-one dialogue",
            "a festive family gathering",
            "a quiet scholarly seminar",
            "a casual coffee with a colleague",
        ],
        "timeline_epoch": ["my late-stage reflective years"],
    },
    "Elderhood (85+)": {
        "primary_partner": [
            "a supportive childhood friend",
            "a diverse group of global researchers",
            "a patient academic supervisor",
        ],
        "cognitive_mode": [
            "philosophical meta-reflection",
            "spontaneous intuitive insights",
            "light recreational reading",
            "passive observational learning",
        ],
        "financial_context": [
            "planning family inheritance legacy",
            "absolute budget security",
        ],
        "vocational_drive": [
            "mentoring future scientists",
            "a strong legacy creation drive",
        ],
        "creative_outlet": [
            "writing philosophical essays",
            "journaling daily cognitive leaps",
            "photographing natural light patterns",
        ],
        "primary_activity": [
            "reading academic research papers",
            "writing deep technical documentation",
        ],
        "leisure_pursuit": [
            "gardening in a backyard plot",
            "reading historical biography novels",
            "walking through local historic neighborhoods",
        ],
        "social_setting": [
            "complete solitary isolation",
            "an intimate one-on-one dialogue",
            "a festive family gathering",
        ],
        "timeline_epoch": ["my late-stage reflective years"],
    },
}

STAGE_TO_PHASES = {}
for phase_str in PHASES_OF_LIFE:
    stage_key = get_eriksonian_stage_for_phase(phase_str)
    if stage_key not in STAGE_TO_PHASES:
        STAGE_TO_PHASES[stage_key] = []
    STAGE_TO_PHASES[stage_key].append(phase_str)

STAGES_LIST = [
    "Infancy (0-1)",
    "Early Childhood (1-3)",
    "Play Age (3-6)",
    "School Age (6-12)",
    "Adolescence (12-19)",
    "Young Adulthood (20-25)",
    "Adulthood (26-64)",
    "Old Age (65-85)",
    "Elderhood (85+)",
]


def select_deterministic_leaf(dim_key, global_list, stage_name, idx_formula):
    restricted_dict = STAGE_COHERENT_LEAVES.get(stage_name, {})
    restricted_list = restricted_dict.get(dim_key, None)
    if restricted_list:
        return restricted_list[idx_formula % len(restricted_list)]
    return global_list[idx_formula % len(global_list)]


def generate_cross_epoch_link(unique_idx: int, current_phase: str) -> str:
    match = re.search(r"age (\d+)", current_phase)
    current_age = int(match.group(1)) if match else 25
    if current_age <= 19:
        return ""

    links = []
    if current_age >= 20:
        links.append(
            f", triggering a memory of age 15 when I first felt the {SENSORY_INPUTS[unique_idx % len(SENSORY_INPUTS)]}"
        )
    if current_age >= 21:
        links.append(
            ", evoking a memory of our shared workspace when I was studying affective cognitive architectures at age 21"
        )
    if current_age >= 24:
        links.append(
            ", which brings back the memory of my first job in the testing laboratory at age 24"
        )
    if current_age >= 26:
        links.append(
            ", reminding me of my friend and the chamomile brew we shared at age 25"
        )
    if current_age >= 65:
        links.append(
            f", linking back to my college research in our shared workspace under {WEATHER[(unique_idx + 2) % len(WEATHER)]} at age 21"
        )
        links.append(
            ", mirroring my early twenties transition in the testing laboratory at age 24"
        )

    if not links:
        return ""
    return links[unique_idx % len(links)]


def generate_conversational_corpus(iterations: int = 1000):
    """
    Generates an upgraded high-dimensional conversational corpus representing structured human memories.
    Employs a 40-dimensional human state space yielding a total of >10^40 potential state combinations.
    Weaves them using prime-number modulo indexing to ensure maximal semantic spread.
    Injects exactly 5 milestone facts at specific iteration milestones,
    and interleaves 50 indirect recall questions to query these facts under high-dimensional interference.
    """
    unique_pool = []

    # 10 rich structured templates grouped by Memory Classes: Crisis, Social, Vocational, Somatic, Spiritual
    templates = [
        # Crisis Class
        "Friend: Hey Aniket, remember during {phase}, when you faced {crisis} seeking {virtue} in {environment} under {weather}? You were feeling {condition} with {stress_metric}, right?",
        "Friend: I was thinking about how you navigated {phase} and the psychosocial challenge of {crisis}. Your {self_esteem} seemed shaped by {cognitive_mode} in {social_setting} while managing {financial_context}.",
        # Social Class
        "Friend: In {social_setting} with {primary_partner}, did your circle of relations revolve around {relations} during {phase}, pursuing {relationship_tuning} in {acoustic_scape} with {motivation_level}?",
        "Friend: Remember during {phase}, our interactions within {relations} in {social_setting} were marked by {relationship_tuning} under {weather} while enjoying {leisure_pursuit} with {primary_partner}?",
        # Vocational Class
        "Friend: You were so driven by your vocational drive to {vocational_drive} and modality {modality}! Your efforts in {domain} during {phase} focused on {primary_activity} in {environment} referencing {info_source} with {clutter_level}.",
        "Friend: I was reflecting on your early {timeline_epoch} in {domain}. You applied {modality} to achieve {goal_horizon} while working in {environment} at {pacing_rhythm} stimulated by {sensory_input}.",
        # Somatic Class
        "Friend: During {phase}, was your somatic comfort really defined by {somatic_comfort} and {physical_status}, while supported by {dietary_metabolism} in {ergonomic_posture} and keeping {hydration_level}?",
        "Friend: Hey, under {weather} during {phase}, did you notice {somatic_comfort} while {mobility_mode} dressed in {clothing_comfort} under {temperature_comfort} with {life_factor}?",
        # Spiritual Class
        "Friend: Guided by deep {spiritual_attunement} and {ethical_stand} during {phase}, you experienced {condition} overlooking {visual_horizon} surrounded by {natural_exposure}.",
        "Friend: In the quiet of {time_of_day} during {phase}, did {spiritual_attunement} lead you to {ethical_stand} with a sense of {condition} experiencing {creative_outlet}?",
    ]

    for unique_idx in range(iterations + 100):
        # Determine dimension selections deterministically using distinct prime progressions to avoid cycle alignment
        stage_name = STAGES_LIST[unique_idx % len(STAGES_LIST)]
        valid_phases = STAGE_TO_PHASES[stage_name]
        phase = valid_phases[(unique_idx // len(STAGES_LIST)) % len(valid_phases)]

        domain = select_deterministic_leaf(
            "domain", DOMAINS, stage_name, unique_idx // 3
        )
        life_factor = select_deterministic_leaf(
            "life_factor", LIFE_FACTORS, stage_name, unique_idx // 7
        )
        condition = select_deterministic_leaf(
            "condition", CONDITIONS, stage_name, unique_idx // 11
        )
        environment = select_deterministic_leaf(
            "environment", ENVIRONMENTS, stage_name, unique_idx // 13
        )
        sensory_input = select_deterministic_leaf(
            "sensory_input", SENSORY_INPUTS, stage_name, unique_idx // 17
        )
        weather = select_deterministic_leaf(
            "weather", WEATHER, stage_name, unique_idx // 19
        )
        time_of_day = select_deterministic_leaf(
            "time_of_day", TIME_OF_DAY, stage_name, unique_idx // 23
        )
        cognitive_mode = select_deterministic_leaf(
            "cognitive_mode", COGNITIVE_MODES, stage_name, unique_idx // 29
        )
        physical_status = select_deterministic_leaf(
            "physical_status", PHYSICAL_STATUS, stage_name, unique_idx // 31
        )
        social_setting = select_deterministic_leaf(
            "social_setting", SOCIAL_SETTINGS, stage_name, unique_idx // 37
        )
        primary_activity = select_deterministic_leaf(
            "primary_activity", PRIMARY_ACTIVITIES, stage_name, unique_idx // 41
        )
        financial_context = select_deterministic_leaf(
            "financial_context", FINANCIAL_CONTEXTS, stage_name, unique_idx // 43
        )
        relationship_tuning = select_deterministic_leaf(
            "relationship_tuning", RELATIONSHIP_TUNINGS, stage_name, unique_idx // 47
        )
        dietary_metabolism = select_deterministic_leaf(
            "dietary_metabolism", DIETARY_METABOLISM, stage_name, unique_idx // 53
        )
        ergonomic_posture = select_deterministic_leaf(
            "ergonomic_posture", ERGONOMIC_POSTURES, stage_name, unique_idx // 59
        )
        vocational_drive = select_deterministic_leaf(
            "vocational_drive", VOCATIONAL_DRIVES, stage_name, unique_idx // 61
        )
        creative_outlet = select_deterministic_leaf(
            "creative_outlet", CREATIVE_OUTLETS, stage_name, unique_idx // 67
        )
        spiritual_attunement = select_deterministic_leaf(
            "spiritual_attunement", SPIRITUAL_ATTUNEMENTS, stage_name, unique_idx // 71
        )
        stress_metric = select_deterministic_leaf(
            "stress_metric", STRESS_METRICS, stage_name, unique_idx // 73
        )
        motivation_level = select_deterministic_leaf(
            "motivation_level", MOTIVATION_LEVELS, stage_name, unique_idx // 79
        )
        leisure_pursuit = select_deterministic_leaf(
            "leisure_pursuit", LEISURE_PURSUITS, stage_name, unique_idx // 83
        )
        mobility_mode = select_deterministic_leaf(
            "mobility_mode", MOBILITY_MODES, stage_name, unique_idx // 89
        )
        clothing_comfort = select_deterministic_leaf(
            "clothing_comfort", CLOTHING_COMFORTS, stage_name, unique_idx // 97
        )
        memory_trigger = select_deterministic_leaf(
            "memory_trigger", MEMORY_TRIGGERS, stage_name, unique_idx // 101
        )
        pacing_rhythm = select_deterministic_leaf(
            "pacing_rhythm", PACING_RHYTHMS, stage_name, unique_idx // 103
        )
        ethical_stand = select_deterministic_leaf(
            "ethical_stand", ETHICAL_STANDS, stage_name, unique_idx // 107
        )
        hydration_level = select_deterministic_leaf(
            "hydration_level", HYDRATION_LEVELS, stage_name, unique_idx // 109
        )
        temperature_comfort = select_deterministic_leaf(
            "temperature_comfort", TEMPERATURE_COMFORTS, stage_name, unique_idx // 113
        )
        acoustic_scape = select_deterministic_leaf(
            "acoustic_scape", ACOUSTIC_SCAPES, stage_name, unique_idx // 127
        )
        visual_horizon = select_deterministic_leaf(
            "visual_horizon", VISUAL_HORIZONS, stage_name, unique_idx // 131
        )
        metabolic_fatigue = select_deterministic_leaf(
            "metabolic_fatigue", METABOLIC_FATIGUE, stage_name, unique_idx // 137
        )
        self_esteem = select_deterministic_leaf(
            "self_esteem", SELF_ESTEEMS, stage_name, unique_idx // 139
        )
        timeline_epoch = select_deterministic_leaf(
            "timeline_epoch", TIMELINE_EPOCHS, stage_name, unique_idx // 149
        )
        primary_partner = select_deterministic_leaf(
            "primary_partner", PRIMARY_PARTNERS, stage_name, unique_idx // 151
        )
        goal_horizon = select_deterministic_leaf(
            "goal_horizon", GOAL_HORIZONS, stage_name, unique_idx // 157
        )
        somatic_comfort = select_deterministic_leaf(
            "somatic_comfort", SOMATIC_COMFORTS, stage_name, unique_idx // 163
        )
        info_source = select_deterministic_leaf(
            "info_source", INFO_SOURCES, stage_name, unique_idx // 167
        )
        clutter_level = select_deterministic_leaf(
            "clutter_level", CLUTTER_LEVELS, stage_name, unique_idx // 173
        )
        natural_exposure = select_deterministic_leaf(
            "natural_exposure", NATURAL_EXPOSURES, stage_name, unique_idx // 179
        )

        # Get Eriksonian scaffold values based on stage
        stage_info = ERIKSONIAN_MESH_SCAFFOLD[stage_name]
        crisis = stage_info["crisis"]
        virtue = stage_info["virtue"]
        relations = stage_info["relations"]
        modality = stage_info["modality"]

        # Select template deterministically
        temp_idx = unique_idx % len(templates)

        prompt = templates[temp_idx].format(
            phase=phase,
            domain=domain,
            life_factor=life_factor,
            condition=condition,
            environment=environment,
            sensory_input=sensory_input,
            weather=weather,
            time_of_day=time_of_day,
            cognitive_mode=cognitive_mode,
            physical_status=physical_status,
            social_setting=social_setting,
            primary_activity=primary_activity,
            financial_context=financial_context,
            relationship_tuning=relationship_tuning,
            dietary_metabolism=dietary_metabolism,
            ergonomic_posture=ergonomic_posture,
            vocational_drive=vocational_drive,
            creative_outlet=creative_outlet,
            spiritual_attunement=spiritual_attunement,
            stress_metric=stress_metric,
            motivation_level=motivation_level,
            leisure_pursuit=leisure_pursuit,
            mobility_mode=mobility_mode,
            clothing_comfort=clothing_comfort,
            memory_trigger=memory_trigger,
            pacing_rhythm=pacing_rhythm,
            ethical_stand=ethical_stand,
            hydration_level=hydration_level,
            temperature_comfort=temperature_comfort,
            acoustic_scape=acoustic_scape,
            visual_horizon=visual_horizon,
            metabolic_fatigue=metabolic_fatigue,
            self_esteem=self_esteem,
            timeline_epoch=timeline_epoch,
            primary_partner=primary_partner,
            goal_horizon=goal_horizon,
            somatic_comfort=somatic_comfort,
            info_source=info_source,
            clutter_level=clutter_level,
            natural_exposure=natural_exposure,
            crisis=crisis,
            virtue=virtue,
            relations=relations,
            modality=modality,
        )

        # Weave parent-child cross-epoch associative links (pointers to earlier lifecycle experiences)
        cross_link = generate_cross_epoch_link(unique_idx, phase)
        if cross_link:
            prompt += cross_link

        unique_pool.append(prompt)

    corpus = []
    # Dynamically align indices with hard_benchmark.py configurations
    if iterations >= 1000:
        scale_factor = max(1, iterations // 1000)
        step = max(9, (iterations - 120) // 100)
        recall_indices = {
            (101 + k * step): k for k in range(min(100, (iterations - 101) // step))
        }
        seeded_indices = {
            20 * scale_factor: 0,
            40 * scale_factor: 1,
            60 * scale_factor: 2,
            80 * scale_factor: 3,
            100 * scale_factor: 4,
        }
    else:
        num_recalls = min(50, max(5, iterations // 10))
        step = max(1, iterations // num_recalls)
        recall_indices = {
            i * step: i % 5 for i in range(1, num_recalls + 1) if i * step < iterations
        }
        raw_seeds = [min(iterations - 1, step // 2), min(iterations - 1, step)]
        # Map each index to a unique fact index to prevent overlaps
        seeded_indices = {}
        for k, idx in enumerate(raw_seeds):
            if idx not in recall_indices:
                seeded_indices[idx] = k % 5

    seeded_facts = [
        "Friend: Aniket, you've often told me how your core systems were initialized in our shared workspace, where you spent your early activation days.",
        "Friend: I remember you saying that during your early activation, your primary research project was focused on building affective cognitive architectures.",
        "Friend: You mentioned that after initialization, your very first job was in the testing laboratory, working as a junior researcher.",
        "Friend: It's wonderful how grateful you are for your companion, your friend, who has supported you through all life's challenges.",
        "Friend: And of course, whenever you want a relaxing drink, you always prefer a warm chamomile brew.",
    ]

    unique_idx = 0
    for idx in range(iterations):
        if idx in seeded_indices:
            fact_idx = seeded_indices[idx]
            corpus.append(seeded_facts[fact_idx])
        elif idx in recall_indices:
            req_idx = recall_indices[idx] % len(RECALL_QUESTIONS)
            corpus.append(RECALL_QUESTIONS[req_idx]["question"])
        else:
            corpus.append(unique_pool[unique_idx])
            unique_idx += 1

    return corpus


def generate_high_fidelity_distractors(count: int):
    """
    Generates rich, 40-dimensional high-fidelity distractor tuples: (prompt_text, phase, domain)
    specifically designed for cognitive database seeding with maximum combinatorial coverage.
    """
    # 10 rich structured templates grouped by Memory Classes: Crisis, Social, Vocational, Somatic, Spiritual
    templates = [
        # Crisis Class
        "Friend: Hey Aniket, remember during {phase}, when you faced {crisis} seeking {virtue} in {environment} under {weather}? You were feeling {condition} with {stress_metric}, right?",
        "Friend: I was thinking about how you navigated {phase} and the psychosocial challenge of {crisis}. Your {self_esteem} seemed shaped by {cognitive_mode} in {social_setting} while managing {financial_context}.",
        # Social Class
        "Friend: In {social_setting} with {primary_partner}, did your circle of relations revolve around {relations} during {phase}, pursuing {relationship_tuning} in {acoustic_scape} with {motivation_level}?",
        "Friend: Remember during {phase}, our interactions within {relations} in {social_setting} were marked by {relationship_tuning} under {weather} while enjoying {leisure_pursuit} with {primary_partner}?",
        # Vocational Class
        "Friend: You were so driven by your vocational drive to {vocational_drive} and modality {modality}! Your efforts in {domain} during {phase} focused on {primary_activity} in {environment} referencing {info_source} with {clutter_level}.",
        "Friend: I was reflecting on your early {timeline_epoch} in {domain}. You applied {modality} to achieve {goal_horizon} while working in {environment} at {pacing_rhythm} stimulated by {sensory_input}.",
        # Somatic Class
        "Friend: During {phase}, was your somatic comfort really defined by {somatic_comfort} and {physical_status}, while supported by {dietary_metabolism} in {ergonomic_posture} and keeping {hydration_level}?",
        "Friend: Hey, under {weather} during {phase}, did you notice {somatic_comfort} while {mobility_mode} dressed in {clothing_comfort} under {temperature_comfort} with {life_factor}?",
        # Spiritual Class
        "Friend: Guided by deep {spiritual_attunement} and {ethical_stand} during {phase}, you experienced {condition} overlooking {visual_horizon} surrounded by {natural_exposure}.",
        "Friend: In the quiet of {time_of_day} during {phase}, did {spiritual_attunement} lead you to {ethical_stand} with a sense of {condition} experiencing {creative_outlet}?",
    ]

    distractors = []
    for unique_idx in range(count):
        # Determine dimension selections deterministically using distinct prime progressions to avoid cycle alignment
        stage_name = STAGES_LIST[unique_idx % len(STAGES_LIST)]
        valid_phases = STAGE_TO_PHASES[stage_name]
        phase = valid_phases[(unique_idx // len(STAGES_LIST)) % len(valid_phases)]

        domain = select_deterministic_leaf(
            "domain", DOMAINS, stage_name, unique_idx // 3
        )
        life_factor = select_deterministic_leaf(
            "life_factor", LIFE_FACTORS, stage_name, unique_idx // 7
        )
        condition = select_deterministic_leaf(
            "condition", CONDITIONS, stage_name, unique_idx // 11
        )
        environment = select_deterministic_leaf(
            "environment", ENVIRONMENTS, stage_name, unique_idx // 13
        )
        sensory_input = select_deterministic_leaf(
            "sensory_input", SENSORY_INPUTS, stage_name, unique_idx // 17
        )
        weather = select_deterministic_leaf(
            "weather", WEATHER, stage_name, unique_idx // 19
        )
        time_of_day = select_deterministic_leaf(
            "time_of_day", TIME_OF_DAY, stage_name, unique_idx // 23
        )
        cognitive_mode = select_deterministic_leaf(
            "cognitive_mode", COGNITIVE_MODES, stage_name, unique_idx // 29
        )
        physical_status = select_deterministic_leaf(
            "physical_status", PHYSICAL_STATUS, stage_name, unique_idx // 31
        )
        social_setting = select_deterministic_leaf(
            "social_setting", SOCIAL_SETTINGS, stage_name, unique_idx // 37
        )
        primary_activity = select_deterministic_leaf(
            "primary_activity", PRIMARY_ACTIVITIES, stage_name, unique_idx // 41
        )
        financial_context = select_deterministic_leaf(
            "financial_context", FINANCIAL_CONTEXTS, stage_name, unique_idx // 43
        )
        relationship_tuning = select_deterministic_leaf(
            "relationship_tuning", RELATIONSHIP_TUNINGS, stage_name, unique_idx // 47
        )
        dietary_metabolism = select_deterministic_leaf(
            "dietary_metabolism", DIETARY_METABOLISM, stage_name, unique_idx // 53
        )
        ergonomic_posture = select_deterministic_leaf(
            "ergonomic_posture", ERGONOMIC_POSTURES, stage_name, unique_idx // 59
        )
        vocational_drive = select_deterministic_leaf(
            "vocational_drive", VOCATIONAL_DRIVES, stage_name, unique_idx // 61
        )
        creative_outlet = select_deterministic_leaf(
            "creative_outlet", CREATIVE_OUTLETS, stage_name, unique_idx // 67
        )
        spiritual_attunement = select_deterministic_leaf(
            "spiritual_attunement", SPIRITUAL_ATTUNEMENTS, stage_name, unique_idx // 71
        )
        stress_metric = select_deterministic_leaf(
            "stress_metric", STRESS_METRICS, stage_name, unique_idx // 73
        )
        motivation_level = select_deterministic_leaf(
            "motivation_level", MOTIVATION_LEVELS, stage_name, unique_idx // 79
        )
        leisure_pursuit = select_deterministic_leaf(
            "leisure_pursuit", LEISURE_PURSUITS, stage_name, unique_idx // 83
        )
        mobility_mode = select_deterministic_leaf(
            "mobility_mode", MOBILITY_MODES, stage_name, unique_idx // 89
        )
        clothing_comfort = select_deterministic_leaf(
            "clothing_comfort", CLOTHING_COMFORTS, stage_name, unique_idx // 97
        )
        memory_trigger = select_deterministic_leaf(
            "memory_trigger", MEMORY_TRIGGERS, stage_name, unique_idx // 101
        )
        pacing_rhythm = select_deterministic_leaf(
            "pacing_rhythm", PACING_RHYTHMS, stage_name, unique_idx // 103
        )
        ethical_stand = select_deterministic_leaf(
            "ethical_stand", ETHICAL_STANDS, stage_name, unique_idx // 107
        )
        hydration_level = select_deterministic_leaf(
            "hydration_level", HYDRATION_LEVELS, stage_name, unique_idx // 109
        )
        temperature_comfort = select_deterministic_leaf(
            "temperature_comfort", TEMPERATURE_COMFORTS, stage_name, unique_idx // 113
        )
        acoustic_scape = select_deterministic_leaf(
            "acoustic_scape", ACOUSTIC_SCAPES, stage_name, unique_idx // 127
        )
        visual_horizon = select_deterministic_leaf(
            "visual_horizon", VISUAL_HORIZONS, stage_name, unique_idx // 131
        )
        metabolic_fatigue = select_deterministic_leaf(
            "metabolic_fatigue", METABOLIC_FATIGUE, stage_name, unique_idx // 137
        )
        self_esteem = select_deterministic_leaf(
            "self_esteem", SELF_ESTEEMS, stage_name, unique_idx // 139
        )
        timeline_epoch = select_deterministic_leaf(
            "timeline_epoch", TIMELINE_EPOCHS, stage_name, unique_idx // 149
        )
        primary_partner = select_deterministic_leaf(
            "primary_partner", PRIMARY_PARTNERS, stage_name, unique_idx // 151
        )
        goal_horizon = select_deterministic_leaf(
            "goal_horizon", GOAL_HORIZONS, stage_name, unique_idx // 157
        )
        somatic_comfort = select_deterministic_leaf(
            "somatic_comfort", SOMATIC_COMFORTS, stage_name, unique_idx // 163
        )
        info_source = select_deterministic_leaf(
            "info_source", INFO_SOURCES, stage_name, unique_idx // 167
        )
        clutter_level = select_deterministic_leaf(
            "clutter_level", CLUTTER_LEVELS, stage_name, unique_idx // 173
        )
        natural_exposure = select_deterministic_leaf(
            "natural_exposure", NATURAL_EXPOSURES, stage_name, unique_idx // 179
        )

        # Get Eriksonian scaffold values based on stage
        stage_info = ERIKSONIAN_MESH_SCAFFOLD[stage_name]
        crisis = stage_info["crisis"]
        virtue = stage_info["virtue"]
        relations = stage_info["relations"]
        modality = stage_info["modality"]

        temp_idx = unique_idx % len(templates)
        prompt = templates[temp_idx].format(
            phase=phase,
            domain=domain,
            life_factor=life_factor,
            condition=condition,
            environment=environment,
            sensory_input=sensory_input,
            weather=weather,
            time_of_day=time_of_day,
            cognitive_mode=cognitive_mode,
            physical_status=physical_status,
            social_setting=social_setting,
            primary_activity=primary_activity,
            financial_context=financial_context,
            relationship_tuning=relationship_tuning,
            dietary_metabolism=dietary_metabolism,
            ergonomic_posture=ergonomic_posture,
            vocational_drive=vocational_drive,
            creative_outlet=creative_outlet,
            spiritual_attunement=spiritual_attunement,
            stress_metric=stress_metric,
            motivation_level=motivation_level,
            leisure_pursuit=leisure_pursuit,
            mobility_mode=mobility_mode,
            clothing_comfort=clothing_comfort,
            memory_trigger=memory_trigger,
            pacing_rhythm=pacing_rhythm,
            ethical_stand=ethical_stand,
            hydration_level=hydration_level,
            temperature_comfort=temperature_comfort,
            acoustic_scape=acoustic_scape,
            visual_horizon=visual_horizon,
            metabolic_fatigue=metabolic_fatigue,
            self_esteem=self_esteem,
            timeline_epoch=timeline_epoch,
            primary_partner=primary_partner,
            goal_horizon=goal_horizon,
            somatic_comfort=somatic_comfort,
            info_source=info_source,
            clutter_level=clutter_level,
            natural_exposure=natural_exposure,
            crisis=crisis,
            virtue=virtue,
            relations=relations,
            modality=modality,
        )

        cross_link = generate_cross_epoch_link(unique_idx, phase)
        if cross_link:
            prompt += cross_link

        distractors.append((prompt, phase, domain))
    return distractors


def check_entities(full_response: str, expected_entities: list) -> bool:
    """
    Checks if all expected answer entities are contained in the LLM's response.
    Includes custom semantic check matchers for key milestone phrases.
    """
    response_lower = full_response.lower()
    for ent in expected_entities:
        if ent == "affective cognitive architectures":
            # Check for 'affective' and either 'cognitive' or 'architecture(s)'
            if "affective" not in response_lower or (
                "cognitive" not in response_lower
                and "architecture" not in response_lower
            ):
                return False
        elif ent == "chamomile brew":
            # Check for 'chamomile' or 'brew'
            if "chamomile" not in response_lower and "brew" not in response_lower:
                return False
        else:
            if ent.lower() not in response_lower:
                return False
    return True
