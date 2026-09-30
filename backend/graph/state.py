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
    approved: list[str]

   
    writer_directions: dict
    repair_attempts: int
    quality_history: list[dict]

   
    story_bible: dict
    draft_facts: list[str]
    stage_warnings: list[str]
    fix_notes: list[str]
    stage_fix_count: int

    
    screenplay_plan: list[dict]      # [{heading, title, summary, characters}]
    screenplay_scenes: list[str]     # Fountain text of each finished scene
    scene_summaries: list[str]       # 1-2 line summary of each finished scene
    screenplay_warnings: list[str]   # format / cast warnings, per scene
    screenplay: str                  # the assembled Fountain script

