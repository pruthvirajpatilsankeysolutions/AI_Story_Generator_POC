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
