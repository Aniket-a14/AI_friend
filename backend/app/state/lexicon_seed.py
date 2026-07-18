"""Generic innate seed for the mental lexicon.

This is the *only* hardcoded lexical data in the memory system, and it is used
strictly as one-time seed data (like seeding a fresh database), never read on the
recall hot path. It represents the small, generic English vocabulary a humanoid
"boots with" before it has lived any conversations -- an infant's early semantic
priming. Everything beyond it is *acquired* from experience and can reinforce,
extend, or out-weigh these seeds over time.

Deliberately generic: these are common everyday English word groups (emotions,
size, time, family, movement, cognition ...). There are NO corpus-, domain-, or
benchmark-specific terms here -- that was the whole point of retiring the old
static ``SYNONYM_MAP``.

``INNATE_CLUSTERS`` are groups of loosely-related words. On first run each cluster
is expanded into all-pairs co-occurrence associations at ``INNATE_WEIGHT`` and the
member words are inserted into ``vocabulary`` with ``source = 'innate'``.
"""

# Modest starting weight for innate associations. Kept low so that a handful of
# real co-occurrences from lived conversation (each +1.0) quickly overtakes and
# reshapes the innate priming rather than being permanently dominated by it.
INNATE_WEIGHT = 2.0

INNATE_CLUSTERS = [
    # affect / emotion
    ["happy", "glad", "joy", "pleased", "cheerful"],
    ["sad", "unhappy", "down", "gloomy", "upset"],
    ["angry", "mad", "annoyed", "furious", "irritated"],
    ["afraid", "scared", "fearful", "anxious", "worried"],
    ["calm", "relaxed", "peaceful", "quiet", "still"],
    ["tired", "sleepy", "exhausted", "weary"],
    # people / relationships
    ["friend", "buddy", "companion", "mate", "pal"],
    ["family", "parent", "mother", "father", "child"],
    ["person", "people", "human", "someone", "everyone"],
    ["love", "adore", "cherish", "care", "affection"],
    # size / quantity
    ["big", "large", "huge", "great", "giant"],
    ["small", "little", "tiny", "minor", "slight"],
    ["many", "much", "lots", "plenty", "several"],
    ["few", "little", "rare", "scarce"],
    # time
    ["now", "today", "present", "current", "moment"],
    ["past", "before", "earlier", "yesterday", "ago"],
    ["future", "later", "soon", "tomorrow", "next"],
    ["always", "forever", "constant", "continual"],
    # cognition / communication
    ["think", "believe", "consider", "reckon", "suppose"],
    ["know", "understand", "realize", "recognize", "aware"],
    ["remember", "recall", "recollect", "memory"],
    ["forget", "lose", "overlook", "miss"],
    ["say", "speak", "talk", "tell", "mention"],
    ["ask", "question", "inquire", "wonder", "query"],
    ["learn", "study", "practice", "train", "develop"],
    # activity / work
    ["work", "job", "task", "labour", "duty"],
    ["make", "build", "create", "form", "produce"],
    ["help", "assist", "support", "aid", "serve"],
    ["play", "game", "fun", "enjoy", "leisure"],
    # movement / place
    ["go", "move", "travel", "leave", "depart"],
    ["come", "arrive", "reach", "approach", "near"],
    ["home", "house", "place", "room", "dwelling"],
    ["walk", "stroll", "wander", "step", "pace"],
    # perception / quality
    ["see", "look", "watch", "observe", "notice"],
    ["hear", "listen", "sound", "noise"],
    ["good", "nice", "fine", "pleasant", "positive"],
    ["bad", "poor", "awful", "negative", "wrong"],
    ["new", "fresh", "recent", "modern", "novel"],
    ["old", "aged", "ancient", "former", "past"],
    # everyday sustenance
    ["eat", "food", "meal", "dine", "feed"],
    ["drink", "water", "beverage", "sip", "thirst"],
    ["sleep", "rest", "nap", "slumber", "bed"],
]
