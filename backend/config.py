STAGES = [
    "concept",
    "logline",
    "characters",
    "conflict",
    "ending",
    "structure",
    "beats",
    "outline",
    "story",
]

LABELS = {
    "concept": "Concept",
    "logline": "Logline",
    "characters": "Characters",
    "conflict": "Conflict",
    "ending": "Ending",
    "structure": "Structure",
    "beats": "Beats",
    "outline": "Outline",
    "story": "Story",
}

CONTENT_TYPES = ["Film Story", "Short Story", "Web Series Pilot", "Novel Chapter"]
GENRES = [
    "Action",
    "Adventure",
    "Comedy",
    "Crime",
    "Drama",
    "Family",
    "Fantasy",
    "Historical",
    "Horror",
    "Musical",
    "Mystery",
    "Mythological",
    "Political",
    "Romance",
    "Sci-Fi",
    "Social Drama",
    "Sports",
    "Supernatural",
    "Thriller",
    "War",
]

TONES = [
    "Dark",
    "Emotional",
    "Epic",
    "Feel-good",
    "Gritty",
    "Heartwarming",
    "Hopeful",
    "Humorous",
    "Inspirational",
    "Intense",
    "Mass / Commercial",
    "Melancholic",
    "Mysterious",
    "Nostalgic",
    "Realistic",
    "Romantic",
    "Satirical",
    "Suspenseful",
    "Tragic",
    "Whimsical",
]


LANGUAGES = [
    "English",
    "Hindi",
    "Tamil",
    "Telugu",
    "Malayalam",
    "Kannada",
    "Marathi",
    "Bengali",
    "Spanish",
    "French",
]

LENGTHS = {
    "Short": {"words": 1000, "scenes": "8-12", "beats": 10},
    "Medium": {"words": 2500, "scenes": "15-20", "beats": 15},
    "Long": {"words": 7000, "scenes": "45-50", "beats": 30},
}

# LENGTHS = {
#     "Short": {"words": 1000, "scenes": "8-12", "beats": 10},
#     "Medium": {"words": 2500, "scenes": "15-20", "beats": 15},
#     "Long": {"words": 4500, "scenes": "25-35", "beats": 15},
# }

REVISION_OPTIONS = [
    "Make it more emotional",
    "Make the protagonist stronger",
    "Increase suspense",
    "Improve the ending",
    "Make it shorter",
    "Make it more cinematic",
]


# ---- Validation -------------------------------------------------------------

# Validator scores are 0-100. A story below this score is repaired, even with
# no hard failures. Hard failures ALWAYS mean FAIL, whatever the score.
REWRITE_THRESHOLD = 80

# How many repair-and-revalidate rounds to run before stopping and reporting.
MAX_REPAIR_ROUNDS = 1

# Problems that make a story FAIL no matter how well it is written.
HARD_FAILURE_TYPES = [
    "character_contradiction",
    "relationship_contradiction",
    "ending_contradiction",
    "major_event_contradiction",
    "location_contradiction",
    "temporal_contradiction",
    "missing_causal_event",
    "missing_object_origin",
    "missing_information_origin",
    "unauthorized_major_character",
    "unauthorized_major_plot_device",
    "reintroduced_rejected_element",
]


STAGE_CONTEXT = {
    "concept": [],
    "logline": ["concept"],
    "characters": ["concept", "logline"],
    "conflict": ["logline", "characters"],
    "ending": ["logline", "characters", "conflict"],
    "structure": ["logline", "characters", "conflict", "ending"],
    "beats": ["characters", "conflict", "ending", "structure"],
    "outline": ["characters", "conflict", "ending", "structure", "beats"],
    "story": ["characters", "conflict", "ending", "outline"],
}
STAGES_WITH_IDEA_ANALYSIS = ["concept"]


CHECKED_STAGES = ["concept", "logline", "characters", "conflict", "ending",
                  "structure", "beats", "outline"]

# How many automatic fix attempts a stage gets before it is shown with warnings.
MAX_STAGE_FIXES = 1

# Keep the Story Bible short so it can go to every stage cheaply.
MAX_FACTS_PER_STAGE = 15



# ---- Screenplay -----------------------------------------------------------------

# Target script length in pages for each story length (1 page ~ 1 minute of screen time).
SCREENPLAY_PAGES = {"Short": 12, "Medium": 30, "Long": 90}
# Rough words per screenplay page, used to size each scene.
SCREENPLAY_WORDS_PER_PAGE = 180
# The outline is turned into at most this many scenes.
SCREENPLAY_MAX_SCENES = 40