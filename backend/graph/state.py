from typing import TypedDict


class StoryState(TypedDict, total=False):
    content_type: str
    idea: str
    genres: list[str]
    tones: list[str]
    language: str
    length: str

    error: str
    idea_analysis: str
    concept: str
    logline: str
    characters: str
    conflict: str
    ending: str
    structure: str
    beats: str
    outline: str
    story: str
    quality_report: dict
    final_story: str
    revisions: list[str]

    current_stage: str
    feedback: str
    # Stage names the writer accepted or edited. Only these are canon.
    approved: list[str]

    # Retry directions the writer gave, per stage, e.g. {"characters": ["remove the cop"]}.
    # Once that stage is approved, its directions are constraints the story must respect.
    writer_directions: dict
    # How many repair rounds have run on the final story.
    repair_attempts: int
    # Every validation report in order (first check, then each re-check).
    quality_history: list[dict]

    # Story Bible: short hard facts from each APPROVED stage, e.g.
    # {"concept": ["Hometown: Pune", "Both families moved in 2016"], ...}
    story_bible: dict
    # Facts extracted from the draft now waiting for review (saved to the bible on Accept).
    draft_facts: list[str]
    # Consistency problems still present in the draft shown to the writer.
    stage_warnings: list[str]
    # Conflicts the auto-fix should correct (empty unless an auto-fix is running).
    fix_notes: list[str]
    # Auto-fix attempts used on the current draft.
    stage_fix_count: int

    
    # Screenplay (written after the final story, one scene at a time)
    screenplay_plan: list[dict]      # [{heading, title, summary, characters}]
    screenplay_scenes: list[str]     # Fountain text of each finished scene
    scene_summaries: list[str]       # 1-2 line summary of each finished scene
    screenplay_warnings: list[str]   # format / cast warnings, per scene
    screenplay: str                  # the assembled Fountain script

