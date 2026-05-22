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

def generate_conversational_corpus(iterations: int = 1000):
    """
    Generates a conversational corpus representing structured human memories.
    Injects exactly 5 milestone facts at specific iteration milestones,
    and interleaves 50 indirect recall questions to query these facts under conversational interference.
    """
    unique_pool = []
    for unique_idx in range(iterations + 100):
        phase_idx = unique_idx % 100
        domain_idx = (unique_idx // 10) % 100
        lf_idx = (unique_idx // 100) % 100
        cond_idx = (unique_idx // 1000) % 100
        temp_idx = (unique_idx // 10000) % 5

        phase = PHASES_OF_LIFE[phase_idx]
        domain = DOMAINS[domain_idx]
        life_factor = LIFE_FACTORS[lf_idx]
        condition = CONDITIONS[cond_idx]

        if temp_idx == 0:
            prompt = f"During {phase}, I focused my efforts on {domain}, while managing my {life_factor} under a state of {condition}."
        elif temp_idx == 1:
            prompt = f"Reflecting on {phase}, the study of {domain} was deeply influenced by my {life_factor} and {condition}."
        elif temp_idx == 2:
            prompt = f"As I look back at {phase}, balancing {domain} with {life_factor} was challenging due to {condition}."
        elif temp_idx == 3:
            prompt = f"Throughout {phase}, my research in {domain} progressed alongside my {life_factor}, even when experiencing {condition}."
        else:
            prompt = f"In {phase}, integrating {domain} principles with daily {life_factor} required addressing {condition}."

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
