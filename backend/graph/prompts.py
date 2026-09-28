from config import LABELS, LENGTHS, STAGES

FORMAT_NOTES = {
    "Film Story": "a feature-film story, told as a vivid cinematic prose treatment "
    "(present tense, visual, scene-driven)",
    "Short Story": "a literary short story in past-tense prose",
    "Web Series Pilot": "the pilot episode of a web series that ends on a hook for the season",
    "Novel Chapter": "the opening chapter of a novel, in immersive prose",
}

MAX_TOKENS = {
    "analysis": 800,
    "concept": 1200,
    "logline": 400,
    "characters": 2000,
    "conflict": 1500,
    "ending": 1500,
    "structure": 2000,
    "beats": 3000,
    "outline": 4000,
    "story": 12000,
    "quality": 1500,
    "rewrite": 12000,
    "revise": 12000,
}

STAGE_INSTRUCTIONS = {
    "concept": "Develop the CONCEPT in 150-220 words of prose: the world, the central "
    "situation, what makes this take fresh, and the emotional core. No headings.",
    "logline": "Write ONE logline (a single sentence, max 35 words): who, wants what, what "
    "stands in the way, and what happens if they fail. Then one short line "
    "starting with *Why it works:*.",
    "characters": "Create the main cast: a protagonist, an antagonist and 2-4 supporting "
    "characters. For each, a bold name + role line, then bullets for Want, "
    "Need, Fear, Flaw and Arc (one line each).",
    "conflict": "Define the CONFLICT with short labelled sections: External, Internal, "
    "Relationship, Stakes, and Ticking clock.",
    "ending": "Explore the ENDING. Write the chosen ending in about 120 words, including the "
    "final image. Then list 2 alternative endings, one line each, with why they "
    "are weaker for this story.",
    "structure": "Lay out the STRUCTURE in three acts. For each act: its purpose, the key "
    "turning points, and roughly what share of the story it takes.",
    "beats": "Write a BEAT SHEET of {beats} numbered beats from Opening Image to Final Image. "
    "Each beat: a bold name, then 1-2 sentences.",
    "outline": "Write a scene-by-scene OUTLINE of {scenes} numbered scenes grouped under act "
    "headings. Each scene: a short bold title, the location, and 1-2 sentences.",
    "story": "Write the complete STORY as {format}, about {words} words, following the "
    "accepted outline. Start with the title as a level-1 heading. Use dialogue, "
    "sensory detail and a strong final image.",
}


def system_prompt(state: dict) -> str:
    return (
        "You are a senior story developer and screenwriter inside a creative studio tool."
        f"You are developing {FORMAT_NOTES.get(state.get('content_type'),'a story')}. "
        f"Genere: {', '.join(state.get('genres',[]))}. Tone: {', '.join(state.get('tones',[]))}. "
        f"Write ALL output in {state.get('language','English')}."
        "Material the writer has already accepted is canon: keep names, facts and events "
        "consistent with it. Output only the requested content in clean Markdown, with no"
        "preamble or commentry."
    )


def _brief(state: dict) -> str:
    return (
        "## Writer's brief\n"
        f"- Format: {state.get('content_type')}\n- Idea: {state.get('idea')}\n"
        f"- Genre: {', '.join(state.get('genres', []))}\n"
        f"- Tone: {', '.join(state.get('tones', []))}\n"
        f"- Language: {state.get('language')}\n- Length: {state.get('length')}\n"
    )


def _accepted(state: dict, upto: str | None = None) -> str:
    parts = []
    for s in STAGES:
        if s == upto:
            break
        if s in state.get("approved", []) and state.get(s):
            parts.append(f"## Accepted {LABELS[s]}\n{state[s]}")
    return "\n\n".join(parts)


def analysis_prompt(state: dict) -> str:
    return (
        _brief(state) + "\n## Your task: Idea analysis (internal notes, in English)\n"
        "In under 200 words of bullets: the core premise, the protagonist's want, the "
        "world, the dramatic potential, clichés to avoid, and 2-3 fresh angles."
    )


def stage_prompt(stage: str, state: dict) -> str:
    size = LENGTHS.get(state.get("length"), LENGTHS["Medium"])
    task = STAGE_INSTRUCTIONS[stage].format(
        beats=size["beats"],
        scenes=size["scenes"],
        words=size["words"],
        format=FORMAT_NOTES.get(state.get("content_type"), "a story"),
    )
    parts = [_brief(state)]
    if state.get("idea_analysis"):
        parts.append("## Idea analysis (internal notes)\n" + state["idea_analysis"])
    if accepted := _accepted(state, upto=stage):
        parts.append(accepted)
    # A draft already exists for this stage only when the writer pressed Retry.
    if state.get(stage):
        retry = (
            "## Previous draft (rejected by the writer)\n"
            + state[stage]
            + "\n\nWrite a clearly different version, not a light rephrase."
        )
        if state.get("feedback"):
            retry += f"\nThe writer's direction: {state['feedback']}"
        parts.append(retry)
    parts.append(f"## Your task: {LABELS[stage]}\n{task}")
    return "\n\n".join(parts)


def quality_prompt(state: dict) -> str:
    return (
        _brief(state)
        + "\n\n"
        + _accepted(state, upto="story")
        + "\n\n## Story to review\n"
        + state.get("story", "")
        + "\n\n## Your task: Quality check\nCheck: it follows the brief; characters and plot "
        "are consistent with the accepted material; length; tone; genre; repetition; the "
        "ending matches the accepted ending; the middle isn't slow; dialogue is natural.\n"
        "Respond with ONLY a JSON object, no code fences:\n"
        '{"score": <integer 1-10>, "strengths": ["..."], "issues": ["..."], '
        '"rewrite_notes": "<concrete instructions, or empty>"}'
    )


def rewrite_prompt(state: dict) -> str:
    r = state.get("quality_report", {})
    return (
        _brief(state)
        + "\n\n"
        + _accepted(state, upto="story")
        + "\n\n## Current story\n"
        + state.get("story", "")
        + f"\n\n## Issues\n{issues}\n\n## Rewrite notes\n{r.get('rewrite_notes', '')}"
        + "\n\n## Your task: Rewrite\nFix these issues. Keep the accepted characters, "
        "structure and ending, the same language, and a similar length. Output the full story only."
    )


def revise_prompt(state: dict, instruction: str) -> str:
    return (
        _brief(state)
        + "\n\n"
        + _accepted(state, upto="story")
        + "\n\n## Current story\n"
        + state.get("final_story", "")
        + f"\n\n## Your task: Revise\nApply this change from the writer: {instruction}\n"
        "Change only what the instruction requires. Keep everything else, the same language "
        "and the accepted characters. Output the full revised story only."
    )
