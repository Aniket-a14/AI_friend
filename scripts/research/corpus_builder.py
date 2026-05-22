import os
import sys
import random
import re

# ==============================================================================
# INDIRECT RECALL QUESTIONS (Indirect mapping to avoid prompt parroting)
# ==============================================================================

RECALL_QUESTIONS = [
    {
        "question": "Can you describe how my hometown childhood influenced my college research topic?",
        "entities": ["Kolkata", "affective cognitive architectures"],
    },
    {
        "question": "Did my university project on college research help me get my first job in my initial employment city?",
        "entities": ["affective cognitive architectures", "Bangalore"],
    },
    {
        "question": "How did moving to my first job city affect my early days with my partner?",
        "entities": ["Bangalore", "Priya"],
    },
    {
        "question": "What sweet dessert do I love to share with my partner?",
        "entities": ["Priya", "sweet rasgulla"],
    },
    {
        "question": "Is my favorite sweet treat a specialty of my birth city?",
        "entities": ["Kolkata", "sweet rasgulla"],
    },
    {
        "question": "How did moving from my hometown to my first employment city shape my early career?",
        "entities": ["Kolkata", "Bangalore"],
    },
    {
        "question": "Did my partner know about the research topic I worked on during college?",
        "entities": ["Priya", "affective cognitive architectures"],
    },
    {
        "question": "What is my favorite sweet dessert, and is it a local specialty of my childhood city?",
        "entities": ["Kolkata", "sweet rasgulla"],
    },
    {
        "question": "Did my university research topic inspire my early work in my first employment city?",
        "entities": ["affective cognitive architectures", "Bangalore"],
    },
    {
        "question": "If I wanted to celebrate my first job with my partner, what dessert would we share?",
        "entities": ["Bangalore", "Priya", "sweet rasgulla"],
    },
    {
        "question": "How do my childhood years in my birth city compare to my college research topic?",
        "entities": ["Kolkata", "affective cognitive architectures"],
    },
    {
        "question": "Did I live in my hometown before moving to start my very first job?",
        "entities": ["Kolkata", "Bangalore"],
    },
    {
        "question": "How does my partner support my continued interest in building my college research system?",
        "entities": ["Priya", "affective cognitive architectures"],
    },
    {
        "question": "Why does my preferred sweet treat always remind me of my childhood days in my birth city?",
        "entities": ["Kolkata", "sweet rasgulla"],
    },
    {
        "question": "Did my first job focus on the same system I researched during my university project?",
        "entities": ["Bangalore", "affective cognitive architectures"],
    },
    {
        "question": "How would you describe the journey from my hometown to meeting my partner?",
        "entities": ["Kolkata", "Priya"],
    },
    {
        "question": "Is my favorite dessert the perfect treat to celebrate the completion of my university project?",
        "entities": ["sweet rasgulla", "affective cognitive architectures"],
    },
    {
        "question": "Can you summarize my transition from my childhood city, to college research, to my first job?",
        "entities": ["Kolkata", "affective cognitive architectures", "Bangalore"],
    },
    {
        "question": "What sweet dessert from my hometown does my partner love to enjoy with me?",
        "entities": ["Kolkata", "Priya", "sweet rasgulla"],
    },
    {
        "question": "Did working in my first job city teach me more about my research topic than my college project?",
        "entities": ["Bangalore", "affective cognitive architectures"],
    },
    {
        "question": "How has my partner helped me reflect on my childhood roots in my birth city?",
        "entities": ["Priya", "Kolkata"],
    },
    {
        "question": "If I wanted to introduce colleagues in my first job city to my favorite sweet treat, what memories would I share?",
        "entities": ["Bangalore", "sweet rasgulla", "Kolkata"],
    },
    {
        "question": "Does my college project on my research topic have any connection to my partner?",
        "entities": ["affective cognitive architectures", "Priya"],
    },
    {
        "question": "Why does my preferred sweet treat hold such a special place in my heart, and who is the person I share it with?",
        "entities": ["sweet rasgulla", "Priya"],
    },
    {
        "question": "How did the culture of my childhood hometown prepare me for my first job in my initial employment city?",
        "entities": ["Kolkata", "Bangalore"],
    },
    {
        "question": "Did I start studying my research topic before or after I met my partner?",
        "entities": ["affective cognitive architectures", "Priya"],
    },
    {
        "question": "What is the favorite sweet treat of the person who spent their first job in my initial employment city?",
        "entities": ["sweet rasgulla", "Bangalore"],
    },
    {
        "question": "How does my hometown compare to the city of my first job?",
        "entities": ["Kolkata", "Bangalore"],
    },
    {
        "question": "Would my university project have been successful without the support of my partner?",
        "entities": ["affective cognitive architectures", "Priya"],
    },
    {
        "question": "If my partner and I travel back to my hometown, what traditional sweet dessert should we buy first?",
        "entities": ["Priya", "Kolkata", "sweet rasgulla"],
    },
    {
        "question": "Did the research team at my first job value my college expertise in my core research topic?",
        "entities": ["Bangalore", "affective cognitive architectures"],
    },
    {
        "question": "How did growing up in my birth city shape my choice to study my university project topic?",
        "entities": ["Kolkata", "affective cognitive architectures"],
    },
    {
        "question": "Did I move directly from my hometown to my first job?",
        "entities": ["Kolkata", "Bangalore"],
    },
    {
        "question": "How does my partner feel about the research topic that I did in university?",
        "entities": ["Priya", "affective cognitive architectures"],
    },
    {
        "question": "Why does my preferred sweet treat from my birth city bring back so many nostalgic childhood feelings?",
        "entities": ["sweet rasgulla", "Kolkata"],
    },
    {
        "question": "How did my first job lay the groundwork for my career, and did my partner join me in that city?",
        "entities": ["Bangalore", "Priya"],
    },
    {
        "question": "Is my favorite sweet treat also loved by my partner?",
        "entities": ["sweet rasgulla", "Priya"],
    },
    {
        "question": "How did my childhood in my birth city inspire my intellectual awakening in building my college project?",
        "entities": ["Kolkata", "affective cognitive architectures"],
    },
    {
        "question": "What would my colleagues in my first job city say if I offered them a traditional sweet treat?",
        "entities": ["Bangalore", "sweet rasgulla"],
    },
    {
        "question": "How does my partner support my professional reflections on my first job?",
        "entities": ["Priya", "Bangalore"],
    },
    {
        "question": "Is my favorite sweet treat from my birth city a favorite of my partner?",
        "entities": ["sweet rasgulla", "Kolkata", "Priya"],
    },
    {
        "question": "Did my research in university help me transition to my first job city?",
        "entities": ["affective cognitive architectures", "Bangalore"],
    },
    {
        "question": "What are the most vivid memories of my childhood city that I have shared with my partner?",
        "entities": ["Kolkata", "Priya"],
    },
    {
        "question": "Did my love for my favorite sweet treat develop during my childhood in my birth city or later in my first job city?",
        "entities": ["sweet rasgulla", "Kolkata", "Bangalore"],
    },
    {
        "question": "How did my academic focus on my research topic influence my daily routines in my first job city?",
        "entities": ["affective cognitive architectures", "Bangalore"],
    },
    {
        "question": "What makes my childhood birth city and my partner so central to my life story?",
        "entities": ["Kolkata", "Priya"],
    },
    {
        "question": "Did I ever buy my favorite sweet treat with my first paycheck in my first job city?",
        "entities": ["sweet rasgulla", "Bangalore"],
    },
    {
        "question": "How did my university years studying my research topic lead to a career in my first job city?",
        "entities": ["affective cognitive architectures", "Bangalore"],
    },
    {
        "question": "What sweet dessert would my partner and I eat to celebrate our memories of my birth city?",
        "entities": ["sweet rasgulla", "Priya", "Kolkata"],
    },
    {
        "question": "Can you summarize how my hometown, my first job city, and my partner define my journey?",
        "entities": ["Kolkata", "Bangalore", "Priya"],
    },
]

# ==============================================================================
# LIFE CORPUS DEFINITIONS
# ==============================================================================

DOMAINS = [
    "computational neuroscience", "quantum thermodynamics", "behavioral economics",
    "molecular biology", "stellar astrophysics", "marine ecology", "organic chemistry",
    "epigenetics", "discrete mathematics", "linguistic anthropology", "analytical chemistry",
    "applied mechanics", "archaeological science", "artificial intelligence", "atmospheric physics",
    "avian biology", "biochemical engineering", "biodiversity conservation", "bioinformatics analysis",
    "biomechanical modeling", "biophysical chemistry", "botanical taxonomy", "cartographic science",
    "cellular pathology", "climatological modeling", "cognitive psychology", "comparative literature",
    "complex analysis", "computational logic", "condensed matter physics", "control systems engineering",
    "cryptographic engineering", "developmental economics", "digital signal processing", "dermatological research",
    "ecological modeling", "econometric modeling", "educational psychology", "electrical engineering",
    "electrochemistry study", "evolutionary developmental biology", "fluid dynamics analysis", "forensic entomology",
    "game theory analysis", "gene regulatory networks", "geomorphological mapping", "glacial hydrology",
    "historical musicology", "human-computer interaction", "immunological profiling", "industrial robotics",
    "information theory research", "inorganic chemistry", "macroeconomic modeling", "materials science engineering",
    "mathematical logic", "microbial ecology", "microclimatology study", "nanophotonics research",
    "neuroendocrinology study", "nuclear engineering", "numerical analysis", "oceanographic profiling",
    "optical physics", "organic synthesis", "paleoanthropological discovery", "parasitological research",
    "particle physics phenomenology", "petrological analysis", "pharmacokinetics modeling", "phonological theory",
    "photovoltaic engineering", "plant physiology", "political philosophy", "polymer chemistry",
    "population genetics", "quantum computing architecture", "quantum electrodynamics", "radiological imaging",
    "renal physiology", "rheumatological research", "seismological monitoring", "sociolinguistic mapping",
    "software engineering architecture", "solid state chemistry", "spectroscopic analysis", "statistical mechanics",
    "structural geology", "superconductivity research", "systems biology networks", "tectonic plate modeling",
    "theoretical cosmology", "thermal engineering design", "toxicological screening", "transcriptomic profiling",
    "urban planning sociology", "virological research", "volcanological monitoring", "wildlife epidemiology",
    "zoological classification"
]

LIFE_FACTORS = [
    "nutritional intake", "circadian rhythm stability", "physical aerobic activity",
    "social connection depth", "financial budget management", "commute duration",
    "ergonomic workspace comfort", "daily caffeine intake", "sleep quality",
    "stress management habits", "hydration tracking", "mindfulness meditation practice",
    "family caregiving duties", "personal hobby progress", "digital screen exposure",
    "living space hygiene", "community service involvement", "intellectual stimulation balance",
    "indoor air quality", "outdoor green space exposure", "vocational alignment",
    "creative writing time", "musical practice duration", "recreational reading volume",
    "financial savings rate", "meal prep consistency", "social media consumption",
    "time spent outdoors", "household chore efficiency", "active learning hours",
    "verbal interaction quality", "physical posture habits", "sleep latency duration",
    "noise pollution exposure", "vitamin D synthesis", "friendship network engagement",
    "romantic relationship harmony", "career trajectory planning", "hobbies exploration activity",
    "micro-break frequency", "task prioritization methods", "workload distribution safety",
    "home organization standards", "cultural activity participation", "spiritual practice alignment",
    "gastrointestinal comfort level", "muscle tone maintenance", "cardiovascular endurance exercises",
    "stretching routine frequency", "ambient light exposure", "professional networking consistency",
    "volunteering hours", "gardening activity duration", "pet ownership interaction",
    "cooking experimentation frequency", "laundry cycle organization", "budget surplus utilization",
    "investment portfolio monitoring", "debt reduction progress", "emergency fund stability",
    "academic lecture attendance", "mentorship session frequency", "journaling consistency",
    "public transport usage", "bicycle commuting frequency", "footwear comfort rating",
    "dental hygiene rigor", "skin care consistency", "water temperature preference",
    "thermostat setting preference", "neighbor interaction frequency", "local shopping frequency",
    "online subscription auditing", "desk clutter organization", "clothing closet simplification",
    "tool repair skill improvement", "DIY project completion", "leisure travel frequency",
    "nature hike duration", "photography exploration activity", "museum visit frequency",
    "theater show attendance", "board game night hosting", "family phone call frequency",
    "letter writing practice", "scrapbooking activity duration", "puzzle solving consistency",
    "language learning streak", "medication adherence accuracy", "allergy symptom severity",
    "cough and cold frequency", "joint mobility levels", "back muscle flexibility",
    "eye strain occurrence", "headache recovery duration", "dental checkup regularity",
    "annual physical screening", "preventative medicine practices", "health insurance coverage",
    "sleep schedule consistency"
]

CONDITIONS = [
    "mild cognitive fatigue", "acute creative flow", "persistent performance anxiety",
    "deep emotional calm", "heightened sensory sensitivity", "chronic mild dehydration",
    "ambient noise distraction", "optimal cognitive readiness", "slight physical restlessness",
    "subtle digital fatigue", "mild depressive mood", "elevated social curiosity",
    "profound physical exhaustion", "acute focus hyperstate", "general life satisfaction",
    "existential reflection mood", "seasonal affective shift", "acute caffeine alert state",
    "moderate social exhaustion", "general ambient optimism", "mild somatic stress",
    "intellectual overstimulation", "chronic time pressure", "calm environmental serenity",
    "elevated competitive drive", "subtle emotional vulnerability", "intense problem-solving fatigue",
    "deep artistic inspiration", "mild background apprehension", "optimal task engagement",
    "transient mental block", "vibrant physical vitality", "mild situational frustration",
    "profound scientific curiosity", "mild sensory overload", "peaceful domestic tranquility",
    "subtle career dissatisfaction", "acute project urgency stress", "elevated altruistic motivation",
    "mild environmental discomfort", "moderate muscle soreness", "heightened intuitive awareness",
    "slight social awkwardness", "intense logical concentration", "warm empathetic connection",
    "subtle nostalgic longing", "mild decision fatigue", "acute multitasking overload",
    "profound intellectual humility", "slight seasonal lethargy", "elevated aesthetic appreciation",
    "mild digestive discomfort", "ambient temperature discomfort", "acute mathematical clarity",
    "subtle romantic anxiety", "general financial confidence", "mild somatic tension",
    "elevated creative confidence", "deep spiritual alignment", "subtle family harmony",
    "intense research motivation", "mild routine boredom", "optimal physical balance",
    "slight cognitive hesitation", "acute emotional stability", "profound existential peace",
    "subtle social integration", "mild work-life imbalance", "elevated collaboration enthusiasm",
    "chronic sleep deprivation state", "ambient light deprivation", "acute analytical sharp state",
    "subtle creative block", "general health confidence", "mild academic pressure",
    "elevated competitive anxiety", "deep professional fulfillment", "subtle domestic friction",
    "intense learning desire", "mild attention deficit state", "optimal recovery sleep quality",
    "slight physical stiffness", "acute strategic mindset", "profound emotional resilience",
    "subtle environmental alignment", "mild professional burnout", "elevated teaching enthusiasm",
    "deep philosophical wonder", "subtle relational harmony", "intense software optimization focus",
    "mild communication fatigue", "optimal physiological state", "slight decision hesitation",
    "acute cognitive agility", "profound moral clarity", "subtle personal growth",
    "mild social detachment", "elevated community trust", "deep intellectual curiosity",
    "subtle emotional maturity"
]

PHASES_OF_LIFE = [
    "my early adolescence at age 15", "my developing years at age 16", "my high school transition at age 17",
    "my senior high school experience at age 18", "my freshman year of university at age 19",
    "my sophomore college year at age 20", "my junior college research phase at age 21",
    "my senior college graduation milestone at age 22", "my early twenties job hunt at age 23",
    "my first entry-level position at age 24", "my initial professional growth at age 25",
    "my career exploration phase at age 26", "my budding professional expertise at age 27",
    "my mid-twenties networking phase at age 28", "my early career stabilization at age 29",
    "my entrance into my thirties at age 30", "my early thirties skill expansion at age 31",
    "my professional consolidation phase at age 32", "my mid-career trajectory shift at age 33",
    "my early thirties domestic settling at age 34", "my mid-thirties personal milestones at age 35",
    "my career path diversification at age 36", "my professional peer mentoring at age 37",
    "my mid-thirties leadership trials at age 38", "my organizational responsibility growth at age 39",
    "my entry into my forties at age 40", "my early forties lifestyle calibration at age 41",
    "my mid-career advisory roles at age 42", "my professional legacy planning at age 43",
    "my early forties community engagement at age 44", "my mid-forties family transitions at age 45",
    "my career re-evaluation phase at age 46", "my intellectual horizon broadening at age 47",
    "my senior leadership tenure at age 48", "my late-forties career reflection at age 49",
    "my entrance into my fifties at age 50", "my senior industry expert role at age 51",
    "my mid-fifties consulting phase at age 52", "my professional writing endeavors at age 53",
    "my late-fifties mentorship focus at age 54", "my retirement planning transitions at age 55",
    "my pre-retirement career wind-down at age 56", "my early retirement explorations at age 57",
    "my late-fifties spiritual awakening at age 58", "my serene life reflections at age 59",
    "my entrance into my sixties at age 60", "my early sixties leisure travels at age 61",
    "my retirement hobbies immersion at age 62", "my mid-sixties voluntary mentoring at age 63",
    "my community legacy contribution at age 64", "my peaceful senior lifestyle at age 65",
    "my late-sixties local volunteering at age 66", "my home gardening explorations at age 67",
    "my childhood nostalgia reflections at age 68", "my family history documentation at age 69",
    "my entrance into my seventies at age 70", "my early seventies contemplation phase at age 71",
    "my quiet elder wisdom advisory roles at age 72", "my late-life journal writing at age 73",
    "my reflective walks in local parks at age 74", "my serene domestic retirement at age 75",
    "my sharing of family heirlooms at age 76", "my light physical health routines at age 77",
    "my humorous storytelling to youngsters at age 78", "my deep quiet elder contentment at age 79",
    "my entrance into my eighties at age 80", "my early eighties family gatherings at age 81",
    "my quiet afternoon tea routines at age 82", "my complete inner peace milestone at age 83",
    "my deep octogenarian reflection at age 84", "my late-teens hobby specialization at age 17",
    "my first college internship trials at age 20", "my university thesis defense week at age 22",
    "my initial post-college residency at age 23", "my professional license certification at age 25",
    "my public speaking debut at age 27", "my promotion to team lead duties at age 29",
    "my home relocation experience at age 31", "my first international business trip at age 33",
    "my mid-career research sabbatical at age 35", "my keynote conference presentation at age 38",
    "my initial venture capital exploration at age 41", "my executive board appointment at age 44",
    "my scientific patent filing year at age 46", "my corporate transformation project at age 49",
    "my industry textbook publication at age 52", "my lifetime contribution award week at age 55",
    "my university guest lecture series at age 58", "my local community center founding at age 61",
    "my writing of a historical novel at age 64", "my family ancestral tree completion at age 67",
    "my local history archives archiving at age 70", "my lifetime achievement dinner speech at age 73",
    "my silver anniversary retirement party at age 75", "my local municipal honor ceremony at age 77",
    "my writing of poetry and essays at age 80", "my golden wedding anniversary celebration at age 82",
    "my community library dedication day at age 83", "my historical legacy preservation week at age 84",
    "my peaceful sunset years milestone at age 84"
]

# ==============================================================================
# ADDITIONAL SEMANTIC DIMENSIONS FOR 40-DIMENSIONAL COGNITIVE STATE SPACE
# ==============================================================================

ENVIRONMENTS = [
    "a cozy wood-paneled study", "a sunlit botanical garden", "a crowded university cafe",
    "a quiet library alcove", "a spacious high-ceilinged workshop", "a modern server room with cooling fans",
    "a peaceful lakeside cabin", "a high-altitude mountain research station"
]
SENSORY_INPUTS = [
    "the scent of rain-dampened earth", "the aroma of dark roasted espresso", "the rhythmic clack of mechanical keyboard keys",
    "the bright neon glow of streetlights", "the soft warmth of a fireplace", "the low hum of distant city traffic",
    "the refreshing taste of peppermint tea", "the crisp clean scent of pine needles"
]
WEATHER = [
    "overcast skies", "a crisp autumn breeze", "heavy monsoon rain",
    "humid summer heat", "gentle winter snowfall", "bright spring sunshine",
    "dense morning fog", "a warm tropical evening"
]
TIME_OF_DAY = [
    "the early dawn light", "the mid-afternoon peak hours", "the golden sunset hour",
    "the quiet midnight silence", "the twilight transition", "late-evening shadows",
    "mid-morning clarity", "a sleepless pre-dawn"
]
COGNITIVE_MODES = [
    "deep algorithmic deduction", "light recreational reading", "passive observational learning",
    "creative brainstorming", "meticulous code debugging", "philosophical meta-reflection",
    "strategic pattern mapping", "spontaneous intuitive insights"
]
PHYSICAL_STATUS = [
    "peak physical vitality", "slight joint stiffness", "mild eye strain",
    "abundant neural stamina", "relaxed bodily ease", "minor muscular tension",
    "perfect cardiovascular balance", "recovering physical strength"
]
SOCIAL_SETTINGS = [
    "complete solitary isolation", "an intimate one-on-one dialogue", "a high-pressure team meeting",
    "a crowded public marketplace", "a quiet scholarly seminar", "a festive family gathering",
    "a professional networking reception", "a casual coffee with a colleague"
]
PRIMARY_ACTIVITIES = [
    "writing deep technical documentation", "analyzing complex data graphs", "refactoring memory store systems",
    "designing neural network layers", "reading academic research papers", "sketching hardware component layouts",
    "solving discrete math equations", "validating local database indices"
]
FINANCIAL_CONTEXTS = [
    "absolute budget security", "conscious resource optimization", "monitoring market portfolios",
    "planning long-term investments", "reviewing monthly budget constraints", "allocating research capital",
    "securing project grants", "planning family inheritance legacy"
]
RELATIONSHIP_TUNINGS = [
    "profound interpersonal harmony", "warm family conversations", "supportive mentor feedback",
    "deep collaboration alignment", "peaceful domestic quietude", "meaningful peer recognition",
    "building new friendship networks", "nurturing close personal ties"
]
DIETARY_METABOLISM = [
    "post-prandial satisfaction", "a sharp caffeine-induced alert state", "slight dehydration signals",
    "perfectly balanced glucose levels", "light nutrient replenishment", "a clean fasted state",
    "the warmth of an herbal beverage", "steady metabolic energy"
]
ERGONOMIC_POSTURES = [
    "upright sitting in an ergonomic chair", "active standing desk alignment", "reclined armchair posture",
    "meticulous upright research posture", "relaxed cushion support", "perfect screen-level gaze",
    "supported spinal extension", "comfortable forearm placement"
]
VOCATIONAL_DRIVES = [
    "intense research curiosity", "a strong legacy creation drive", "perfect vocational alignment",
    "solving real-world human challenges", "seeking structural perfection", "optimizing modular system efficiency",
    "pioneering novel cognitive pipelines", "mentoring future scientists"
]
CREATIVE_OUTLETS = [
    "writing philosophical essays", "sketching architectural concepts", "composing atmospheric music",
    "journaling daily cognitive leaps", "crafting intricate physical models", "programming beautiful user interfaces",
    "photographing natural light patterns", "designing interactive systems"
]
SPIRITUAL_ATTUNEMENTS = [
    "deep meditative presence", "profound existential peace", "cosmic philosophical wonder",
    "quiet personal mindfulness", "holistic natural alignment", "harmonious inner silence",
    "intellectual humility exploration", "contemplative analytical calm"
]
STRESS_METRICS = [
    "absolute tranquil calm", "low-grade background urgency", "acute deadline focus",
    "steady situational confidence", "patient methodical progress", "a structured challenge response",
    "relaxed mental pacing", "a mindful stress-release state"
]
MOTIVATION_LEVELS = [
    "high dopamine-driven reward seeking", "steady task-oriented execution", "post-milestone relaxation",
    "eager anticipation of testing results", "curious exploratory motivation", "focused problem-solving energy",
    "deep intrinsic satisfaction", "enthusiastic collaborative drive"
]
LEISURE_PURSUITS = [
    "playing complex strategy board games", "gardening in a backyard plot", "reading historical biography novels",
    "restoring old mechanical tools", "solving challenging crossword puzzles", "cooking elaborate traditional dishes",
    "walking through local historic neighborhoods", "building custom desktop rigs"
]
MOBILITY_MODES = [
    "walking slowly along a path", "riding a commuter bicycle", "sitting on a public transport bus",
    "standing on a moving train", "relaxing in a stationary vehicle", "climbing a gentle hillside",
    "navigating a busy urban sidewalk", "resting in a quiet room"
]
CLOTHING_COMFORTS = [
    "soft breathable cotton garments", "a cozy heavy wool sweater", "crisp formal research attire",
    "relaxed casual home wear", "a warm weather-resistant jacket", "perfectly broken-in leather shoes",
    "light active athletic wear", "layered comfortable clothing"
]
MEMORY_TRIGGERS = [
    "glancing at an old faded photograph", "hearing a nostalgic melody", "finding a handwritten note",
    "opening a vintage textbook", "catching the aroma of childhood cooking", "revisiting a familiar landscape",
    "encountering a historical artifact", "recalling a vivid past dream"
]
PACING_RHYTHMS = [
    "a meticulous slow pace", "a rapid focused sprint", "a natural comfortable flow",
    "a deliberate step-by-step progress", "an intense uninterrupted focus session", "a patient observational stance",
    "a highly flexible dynamic pace", "a structured routine schedule"
]
ETHICAL_STANDS = [
    "reflecting on societal contribution", "ensuring cognitive safety boundaries", "prioritizing open-source access",
    "advocating for human-centric design", "considering global environmental footprints", "pursuing honest academic rigor",
    "supporting collaborative community growth", "defending scientific integrity"
]
HYDRATION_LEVELS = [
    "perfectly hydrated with pure water", "sipping warm organic green tea", "enjoying a cold refreshing beverage",
    "rehydrating post-workout", "savoring a warm spiced chai", "drinking chilled mineral water",
    "sipping hot chamomile tea", "balanced fluid homeostasis"
]
TEMPERATURE_COMFORTS = [
    "a mild balanced indoor climate", "a cool refreshing air-conditioned room", "cozy radial hearth warmth",
    "a fresh breezy outdoor current", "comfortably warm summer evening air", "a crisp insulated winter shelter",
    "a shaded cool retreat", "a sun-warmed workspace spot"
]
ACOUSTIC_SCAPES = [
    "complete absolute silence", "soft classical ambient piano", "a low-frequency pink noise background",
    "distant birds singing outside", "the gentle rustle of leaves", "a quiet muffled office hum",
    "a gentle rhythmic ticking clock", "soft acoustic guitar frequencies"
]
VISUAL_HORIZONS = [
    "a wide open green landscape", "dual high-resolution monitor screens", "detailed circuit blueprint diagrams",
    "a bookshelf packed with scientific texts", "a clean minimalist desk workspace", "an expansive window view of the sky",
    "a vibrant chalkboard covered in math", "a warm softlylit room interior"
]
METABOLIC_FATIGUE = [
    "unlimited physical stamina", "needing a structured micro-break", "a state of perfect recovery sleep",
    "light physical replenishment", "rested and fully recharged", "steady muscle recovery",
    "balanced neural resource allocation", "optimizing metabolic efficiency"
]
SELF_ESTEEMS = [
    "high academic confidence", "profound professional humility", "quiet self-assured trust",
    "proud of creative milestones", "eager for peer feedback", "objective self-assessment focus",
    "grounded personal resilience", "a mindset of continuous growth"
]
TIMELINE_EPOCHS = [
    "my early formative childhood", "my early twenties transition", "my senior research specialist era",
    "my initial professional launch years", "my mid-career consolidation phase", "my late-stage reflective years",
    "my post-university expansion period", "my collaborative group project tenure"
]
PRIMARY_PARTNERS = [
    "a trusted senior research mentor", "an eager junior university peer", "a brilliant software engineer colleague",
    "a supportive childhood friend", "an expert external patent examiner", "a collaborative database administrator",
    "a diverse group of global researchers", "a patient academic supervisor"
]
GOAL_HORIZONS = [
    "an immediate short-term daily goal", "a quarterly project deadline milestone", "a multi-year career path target",
    "a lifelong legacy contribution", "a weekly sprint objective", "an annual system audit milestone",
    "a temporary exploratory target", "a solid operational benchmark target"
]
SOMATIC_COMFORTS = [
    "fully relaxed neck and shoulders", "flexible and stretched back muscles", "loose warm hand joints",
    "perfect spinal column support", "stamina-filled dynamic posture", "perfectly comfortable seated base",
    "light refreshed physical state", "relaxed eye muscles"
]
INFO_SOURCES = [
    "peer-reviewed academic journal papers", "dense technical documentation manuals", "curated database resource catalogs",
    "collaborative wiki articles", "historical patent office archives", "open-source software repositories",
    "direct physical sensor telemetry", "comprehensive textbook chapters"
]
CLUTTER_LEVELS = [
    "a perfectly pristine clean desk", "a minimalist organized workspace", "a few neatly stacked notebooks",
    "a clean table with a single device", "a highly functional workspace layout", "a structured reference material stack",
    "a spotless laboratory workbench", "an uncluttered digital directory"
]
NATURAL_EXPOSURES = [
    "abundant desk plant foliage", "a large window showing green trees", "frequent short walks in a local park",
    "fresh outdoor mountain air", "the grounding presence of nature", "a nearby office botanical terrace",
    "natural ambient lighting", "views of natural water features"
]

def generate_conversational_corpus(iterations: int = 1000):
    """
    Generates an upgraded high-dimensional conversational corpus representing structured human memories.
    Employs a 40-dimensional human state space yielding a total of >10^40 potential state combinations.
    Weaves them using prime-number modulo indexing to ensure maximal semantic spread.
    Injects exactly 5 milestone facts at specific iteration milestones,
    and interleaves 50 indirect recall questions to query these facts under high-dimensional interference.
    """
    unique_pool = []
    
    # 10 rich natural-language templates weaving different subsets of the 40 dimensions
    templates = [
        # Template 0
        "Weaving back to {timeline_epoch} in {environment}, under {weather} during {time_of_day}, I engaged in {cognitive_mode} while {primary_activity}, focused by {sensory_input} and dressed in {clothing_comfort}.",
        # Template 1
        "During {phase}, my efforts in {domain} were paired with {life_factor} while in a state of {condition}, experiencing {physical_status}, supported by {dietary_metabolism} in {ergonomic_posture} under {stress_metric}.",
        # Template 2
        "In {social_setting} with {primary_partner}, driven by {vocational_drive}, I explored {creative_outlet} with {motivation_level} at {pacing_rhythm}, referencing {info_source} within {clutter_level}.",
        # Template 3
        "Under {weather} at {time_of_day}, while {primary_activity}, I was {mobility_mode}, accompanied by {sensory_input}, keeping {hydration_level} in {temperature_comfort} amidst {acoustic_scape} with {visual_horizon}.",
        # Template 4
        "During {phase}, deep {spiritual_attunement} guided my {leisure_pursuit}, leading me to {ethical_stand} with {self_esteem} toward {goal_horizon}, feeling {somatic_comfort} in {natural_exposure}.",
        # Template 5
        "Reflecting on {timeline_epoch} in {domain}, situated inside {environment}, I adopted {cognitive_mode} with {physical_status} in search of {vocational_drive}, sustaining {stress_metric} in {clutter_level}.",
        # Template 6
        "In {phase}, navigating {social_setting} while {primary_activity}, I nurtured {relationship_tuning} at {pacing_rhythm}, enjoying {hydration_level} within {acoustic_scape} alongside {primary_partner}.",
        # Template 7
        "Inside {environment} during {weather}, my {cognitive_mode} allowed me to focus on {primary_activity}, stimulated by {sensory_input}, fueled by {dietary_metabolism} as I pursued {creative_outlet} overlooking {visual_horizon}.",
        # Template 8
        "Throughout {timeline_epoch}, balancing {life_factor} under a state of {condition} in {ergonomic_posture}, I integrated {spiritual_attunement} and {ethical_stand} towards {goal_horizon} with {somatic_comfort}.",
        # Template 9
        "In {social_setting}, balancing {financial_context} and {relationship_tuning}, I felt {motivation_level} during {leisure_pursuit} while {mobility_mode} in {temperature_comfort} surrounded by {natural_exposure}."
    ]

    for unique_idx in range(iterations + 100):
        # Determine dimension selections deterministically using distinct prime progressions to avoid cycle alignment
        phase = PHASES_OF_LIFE[unique_idx % len(PHASES_OF_LIFE)]
        domain = DOMAINS[(unique_idx // 3) % len(DOMAINS)]
        life_factor = LIFE_FACTORS[(unique_idx // 7) % len(LIFE_FACTORS)]
        condition = CONDITIONS[(unique_idx // 11) % len(CONDITIONS)]
        environment = ENVIRONMENTS[(unique_idx // 13) % len(ENVIRONMENTS)]
        sensory_input = SENSORY_INPUTS[(unique_idx // 17) % len(SENSORY_INPUTS)]
        weather = WEATHER[(unique_idx // 19) % len(WEATHER)]
        time_of_day = TIME_OF_DAY[(unique_idx // 23) % len(TIME_OF_DAY)]
        cognitive_mode = COGNITIVE_MODES[(unique_idx // 29) % len(COGNITIVE_MODES)]
        physical_status = PHYSICAL_STATUS[(unique_idx // 31) % len(PHYSICAL_STATUS)]
        social_setting = SOCIAL_SETTINGS[(unique_idx // 37) % len(SOCIAL_SETTINGS)]
        primary_activity = PRIMARY_ACTIVITIES[(unique_idx // 41) % len(PRIMARY_ACTIVITIES)]
        financial_context = FINANCIAL_CONTEXTS[(unique_idx // 43) % len(FINANCIAL_CONTEXTS)]
        relationship_tuning = RELATIONSHIP_TUNINGS[(unique_idx // 47) % len(RELATIONSHIP_TUNINGS)]
        dietary_metabolism = DIETARY_METABOLISM[(unique_idx // 53) % len(DIETARY_METABOLISM)]
        ergonomic_posture = ERGONOMIC_POSTURES[(unique_idx // 59) % len(ERGONOMIC_POSTURES)]
        vocational_drive = VOCATIONAL_DRIVES[(unique_idx // 61) % len(VOCATIONAL_DRIVES)]
        creative_outlet = CREATIVE_OUTLETS[(unique_idx // 67) % len(CREATIVE_OUTLETS)]
        spiritual_attunement = SPIRITUAL_ATTUNEMENTS[(unique_idx // 71) % len(SPIRITUAL_ATTUNEMENTS)]
        stress_metric = STRESS_METRICS[(unique_idx // 73) % len(STRESS_METRICS)]
        motivation_level = MOTIVATION_LEVELS[(unique_idx // 79) % len(MOTIVATION_LEVELS)]
        leisure_pursuit = LEISURE_PURSUITS[(unique_idx // 83) % len(LEISURE_PURSUITS)]
        mobility_mode = MOBILITY_MODES[(unique_idx // 89) % len(MOBILITY_MODES)]
        clothing_comfort = CLOTHING_COMFORTS[(unique_idx // 97) % len(CLOTHING_COMFORTS)]
        memory_trigger = MEMORY_TRIGGERS[(unique_idx // 101) % len(MEMORY_TRIGGERS)]
        pacing_rhythm = PACING_RHYTHMS[(unique_idx // 103) % len(PACING_RHYTHMS)]
        ethical_stand = ETHICAL_STANDS[(unique_idx // 107) % len(ETHICAL_STANDS)]
        hydration_level = HYDRATION_LEVELS[(unique_idx // 109) % len(HYDRATION_LEVELS)]
        temperature_comfort = TEMPERATURE_COMFORTS[(unique_idx // 113) % len(TEMPERATURE_COMFORTS)]
        acoustic_scape = ACOUSTIC_SCAPES[(unique_idx // 127) % len(ACOUSTIC_SCAPES)]
        visual_horizon = VISUAL_HORIZONS[(unique_idx // 131) % len(VISUAL_HORIZONS)]
        metabolic_fatigue = METABOLIC_FATIGUE[(unique_idx // 137) % len(METABOLIC_FATIGUE)]
        self_esteem = SELF_ESTEEMS[(unique_idx // 139) % len(SELF_ESTEEMS)]
        timeline_epoch = TIMELINE_EPOCHS[(unique_idx // 149) % len(TIMELINE_EPOCHS)]
        primary_partner = PRIMARY_PARTNERS[(unique_idx // 151) % len(PRIMARY_PARTNERS)]
        goal_horizon = GOAL_HORIZONS[(unique_idx // 157) % len(GOAL_HORIZONS)]
        somatic_comfort = SOMATIC_COMFORTS[(unique_idx // 163) % len(SOMATIC_COMFORTS)]
        info_source = INFO_SOURCES[(unique_idx // 167) % len(INFO_SOURCES)]
        clutter_level = CLUTTER_LEVELS[(unique_idx // 173) % len(CLUTTER_LEVELS)]
        natural_exposure = NATURAL_EXPOSURES[(unique_idx // 179) % len(NATURAL_EXPOSURES)]

        # Select template deterministically
        temp_idx = unique_idx % len(templates)
        
        prompt = templates[temp_idx].format(
            phase=phase, domain=domain, life_factor=life_factor, condition=condition,
            environment=environment, sensory_input=sensory_input, weather=weather,
            time_of_day=time_of_day, cognitive_mode=cognitive_mode, physical_status=physical_status,
            social_setting=social_setting, primary_activity=primary_activity, financial_context=financial_context,
            relationship_tuning=relationship_tuning, dietary_metabolism=dietary_metabolism,
            ergonomic_posture=ergonomic_posture, vocational_drive=vocational_drive,
            creative_outlet=creative_outlet, spiritual_attunement=spiritual_attunement,
            stress_metric=stress_metric, motivation_level=motivation_level,
            leisure_pursuit=leisure_pursuit, mobility_mode=mobility_mode,
            clothing_comfort=clothing_comfort, memory_trigger=memory_trigger,
            pacing_rhythm=pacing_rhythm, ethical_stand=ethical_stand,
            hydration_level=hydration_level, temperature_comfort=temperature_comfort,
            acoustic_scape=acoustic_scape, visual_horizon=visual_horizon,
            metabolic_fatigue=metabolic_fatigue, self_esteem=self_esteem,
            timeline_epoch=timeline_epoch, primary_partner=primary_partner,
            goal_horizon=goal_horizon, somatic_comfort=somatic_comfort,
            info_source=info_source, clutter_level=clutter_level,
            natural_exposure=natural_exposure
        )
        unique_pool.append(prompt)

    corpus = []
    if iterations < 105:
        return unique_pool[:iterations]

    scale_factor = max(1, iterations // 1000)
    seeded_indices = {
        20 * scale_factor: 0,
        40 * scale_factor: 1,
        60 * scale_factor: 2,
        80 * scale_factor: 3,
        100 * scale_factor: 4,
    }
    
    seeded_facts = [
        "I was born and raised in Kolkata, a beautiful city where I spent my childhood years.",
        "During my college years, my primary research project was focused on building affective cognitive architectures.",
        "After graduating, my very first job was in Bangalore, working as a junior researcher.",
        "I am incredibly grateful for my partner Priya, who has supported me through all life's challenges.",
        "Whenever I want a dessert, I always prefer a traditional sweet rasgulla.",
    ]

    recall_indices = {(101 + k * 18) * scale_factor: k for k in range(min(50, (iterations - 101) // 18 + 1))}

    unique_idx = 0
    for idx in range(iterations):
        if idx in seeded_indices:
            fact_idx = seeded_indices[idx]
            corpus.append(seeded_facts[fact_idx])
        elif idx in recall_indices:
            req_idx = recall_indices[idx]
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
    templates = [
        # Template 0
        "Weaving back to {timeline_epoch} in {environment}, under {weather} during {time_of_day}, I engaged in {cognitive_mode} while {primary_activity}, focused by {sensory_input} and dressed in {clothing_comfort}.",
        # Template 1
        "During {phase}, my efforts in {domain} were paired with {life_factor} while in a state of {condition}, experiencing {physical_status}, supported by {dietary_metabolism} in {ergonomic_posture} under {stress_metric}.",
        # Template 2
        "In {social_setting} with {primary_partner}, driven by {vocational_drive}, I explored {creative_outlet} with {motivation_level} at {pacing_rhythm}, referencing {info_source} within {clutter_level}.",
        # Template 3
        "Under {weather} at {time_of_day}, while {primary_activity}, I was {mobility_mode}, accompanied by {sensory_input}, keeping {hydration_level} in {temperature_comfort} amidst {acoustic_scape} with {visual_horizon}.",
        # Template 4
        "During {phase}, deep {spiritual_attunement} guided my {leisure_pursuit}, leading me to {ethical_stand} with {self_esteem} toward {goal_horizon}, feeling {somatic_comfort} in {natural_exposure}.",
        # Template 5
        "Reflecting on {timeline_epoch} in {domain}, situated inside {environment}, I adopted {cognitive_mode} with {physical_status} in search of {vocational_drive}, sustaining {stress_metric} in {clutter_level}.",
        # Template 6
        "In {phase}, navigating {social_setting} while {primary_activity}, I nurtured {relationship_tuning} at {pacing_rhythm}, enjoying {hydration_level} within {acoustic_scape} alongside {primary_partner}.",
        # Template 7
        "Inside {environment} during {weather}, my {cognitive_mode} allowed me to focus on {primary_activity}, stimulated by {sensory_input}, fueled by {dietary_metabolism} as I pursued {creative_outlet} overlooking {visual_horizon}.",
        # Template 8
        "Throughout {timeline_epoch}, balancing {life_factor} under a state of {condition} in {ergonomic_posture}, I integrated {spiritual_attunement} and {ethical_stand} towards {goal_horizon} with {somatic_comfort}.",
        # Template 9
        "In {social_setting}, balancing {financial_context} and {relationship_tuning}, I felt {motivation_level} during {leisure_pursuit} while {mobility_mode} in {temperature_comfort} surrounded by {natural_exposure}."
    ]

    distractors = []
    for unique_idx in range(count):
        phase = PHASES_OF_LIFE[unique_idx % len(PHASES_OF_LIFE)]
        domain = DOMAINS[(unique_idx // 3) % len(DOMAINS)]
        life_factor = LIFE_FACTORS[(unique_idx // 7) % len(LIFE_FACTORS)]
        condition = CONDITIONS[(unique_idx // 11) % len(CONDITIONS)]
        environment = ENVIRONMENTS[(unique_idx // 13) % len(ENVIRONMENTS)]
        sensory_input = SENSORY_INPUTS[(unique_idx // 17) % len(SENSORY_INPUTS)]
        weather = WEATHER[(unique_idx // 19) % len(WEATHER)]
        time_of_day = TIME_OF_DAY[(unique_idx // 23) % len(TIME_OF_DAY)]
        cognitive_mode = COGNITIVE_MODES[(unique_idx // 29) % len(COGNITIVE_MODES)]
        physical_status = PHYSICAL_STATUS[(unique_idx // 31) % len(PHYSICAL_STATUS)]
        social_setting = SOCIAL_SETTINGS[(unique_idx // 37) % len(SOCIAL_SETTINGS)]
        primary_activity = PRIMARY_ACTIVITIES[(unique_idx // 41) % len(PRIMARY_ACTIVITIES)]
        financial_context = FINANCIAL_CONTEXTS[(unique_idx // 43) % len(FINANCIAL_CONTEXTS)]
        relationship_tuning = RELATIONSHIP_TUNINGS[(unique_idx // 47) % len(RELATIONSHIP_TUNINGS)]
        dietary_metabolism = DIETARY_METABOLISM[(unique_idx // 53) % len(DIETARY_METABOLISM)]
        ergonomic_posture = ERGONOMIC_POSTURES[(unique_idx // 59) % len(ERGONOMIC_POSTURES)]
        vocational_drive = VOCATIONAL_DRIVES[(unique_idx // 61) % len(VOCATIONAL_DRIVES)]
        creative_outlet = CREATIVE_OUTLETS[(unique_idx // 67) % len(CREATIVE_OUTLETS)]
        spiritual_attunement = SPIRITUAL_ATTUNEMENTS[(unique_idx // 71) % len(SPIRITUAL_ATTUNEMENTS)]
        stress_metric = STRESS_METRICS[(unique_idx // 73) % len(STRESS_METRICS)]
        motivation_level = MOTIVATION_LEVELS[(unique_idx // 79) % len(MOTIVATION_LEVELS)]
        leisure_pursuit = LEISURE_PURSUITS[(unique_idx // 83) % len(LEISURE_PURSUITS)]
        mobility_mode = MOBILITY_MODES[(unique_idx // 89) % len(MOBILITY_MODES)]
        clothing_comfort = CLOTHING_COMFORTS[(unique_idx // 97) % len(CLOTHING_COMFORTS)]
        memory_trigger = MEMORY_TRIGGERS[(unique_idx // 101) % len(MEMORY_TRIGGERS)]
        pacing_rhythm = PACING_RHYTHMS[(unique_idx // 103) % len(PACING_RHYTHMS)]
        ethical_stand = ETHICAL_STANDS[(unique_idx // 107) % len(ETHICAL_STANDS)]
        hydration_level = HYDRATION_LEVELS[(unique_idx // 109) % len(HYDRATION_LEVELS)]
        temperature_comfort = TEMPERATURE_COMFORTS[(unique_idx // 113) % len(TEMPERATURE_COMFORTS)]
        acoustic_scape = ACOUSTIC_SCAPES[(unique_idx // 127) % len(ACOUSTIC_SCAPES)]
        visual_horizon = VISUAL_HORIZONS[(unique_idx // 131) % len(VISUAL_HORIZONS)]
        metabolic_fatigue = METABOLIC_FATIGUE[(unique_idx // 137) % len(METABOLIC_FATIGUE)]
        self_esteem = SELF_ESTEEMS[(unique_idx // 139) % len(SELF_ESTEEMS)]
        timeline_epoch = TIMELINE_EPOCHS[(unique_idx // 149) % len(TIMELINE_EPOCHS)]
        primary_partner = PRIMARY_PARTNERS[(unique_idx // 151) % len(PRIMARY_PARTNERS)]
        goal_horizon = GOAL_HORIZONS[(unique_idx // 157) % len(GOAL_HORIZONS)]
        somatic_comfort = SOMATIC_COMFORTS[(unique_idx // 163) % len(SOMATIC_COMFORTS)]
        info_source = INFO_SOURCES[(unique_idx // 167) % len(INFO_SOURCES)]
        clutter_level = CLUTTER_LEVELS[(unique_idx // 173) % len(CLUTTER_LEVELS)]
        natural_exposure = NATURAL_EXPOSURES[(unique_idx // 179) % len(NATURAL_EXPOSURES)]

        temp_idx = unique_idx % len(templates)
        prompt = templates[temp_idx].format(
            phase=phase, domain=domain, life_factor=life_factor, condition=condition,
            environment=environment, sensory_input=sensory_input, weather=weather,
            time_of_day=time_of_day, cognitive_mode=cognitive_mode, physical_status=physical_status,
            social_setting=social_setting, primary_activity=primary_activity, financial_context=financial_context,
            relationship_tuning=relationship_tuning, dietary_metabolism=dietary_metabolism,
            ergonomic_posture=ergonomic_posture, vocational_drive=vocational_drive,
            creative_outlet=creative_outlet, spiritual_attunement=spiritual_attunement,
            stress_metric=stress_metric, motivation_level=motivation_level,
            leisure_pursuit=leisure_pursuit, mobility_mode=mobility_mode,
            clothing_comfort=clothing_comfort, memory_trigger=memory_trigger,
            pacing_rhythm=pacing_rhythm, ethical_stand=ethical_stand,
            hydration_level=hydration_level, temperature_comfort=temperature_comfort,
            acoustic_scape=acoustic_scape, visual_horizon=visual_horizon,
            metabolic_fatigue=metabolic_fatigue, self_esteem=self_esteem,
            timeline_epoch=timeline_epoch, primary_partner=primary_partner,
            goal_horizon=goal_horizon, somatic_comfort=somatic_comfort,
            info_source=info_source, clutter_level=clutter_level,
            natural_exposure=natural_exposure
        )
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
                "cognitive" not in response_lower and "architecture" not in response_lower
            ):
                return False
        elif ent == "sweet rasgulla":
            # Check for 'rasgulla' or 'sweet rasgulla'
            if "rasgulla" not in response_lower:
                return False
        else:
            if ent.lower() not in response_lower:
                return False
    return True
