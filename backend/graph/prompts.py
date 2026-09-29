import json

from config import (
    HARD_FAILURE_TYPES,
    LABELS,
    LENGTHS,
    MAX_FACTS_PER_STAGE,
    STAGE_CONTEXT,
    STAGES_WITH_IDEA_ANALYSIS,
)

from .canon import (
    current_story,
    format_bible,
    format_canon,
    format_directions,
    get_approved_canon,
    get_writer_directions,
)

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
    "quality": 3500,
    "check": 1200,
    "extract": 800,
    "rewrite": 12000,
    "revise": 12000,
}

STAGE_INSTRUCTIONS = {
    "concept": "Develop the CONCEPT in 150-220 words of prose: the world, the central "
    "situation, what makes this take fresh, and the emotional core. No headings. "
    "State the concrete facts plainly: the city or town where the story happens, where "
    "each main character lives now, the time frame, and what happened in the past "
    "(who did what, and why).",
    "logline": "Write ONE logline (a single sentence, max 35 words): who, wants what, what "
    "stands in the way, and what happens if they fail. Then one short line "
    "starting with *Why it works:*.",
    "characters": "Create the main cast: a protagonist, an antagonist and 2-4 supporting "
    "characters. For each, a bold name + role line, then bullets for Want, "
    "Need, Fear, Flaw and Arc (one line each). Every arc must be something that can "
    "visibly happen on-page within this story's time frame.",
    "conflict": "Define the CONFLICT with short labelled sections: External, Internal, "
    "Relationship, Stakes, and Ticking clock.",
    "ending": "Explore the ENDING. Write the chosen ending in about 120 words, including the "
    "final image. Then list 2 alternative endings, one line each, with why they "
    "are weaker for this story.",
    "structure": "Lay out the STRUCTURE in three acts. For each act: its purpose, the key "
    "turning points, and roughly what share of the story it takes.",
    "beats": "Write a BEAT SHEET of {beats} numbered beats from Opening Image to Final Image. "
    "Each beat: a bold name, then 1-2 sentences. Include a beat that pays off every "
    "character arc in the Story Bible, and include the approved ending's key actions "
    "exactly as approved.",
    "outline": "Write a scene-by-scene OUTLINE of {scenes} numbered scenes grouped under act "
    "headings. Each scene: a short bold title, the location, and 1-2 sentences. Every "
    "approved beat must appear in at least one scene, and every important event must "
    "have its cause shown in an earlier scene.",
    "story": "Write the complete STORY as {format}, about {words} words, following the "
    "approved outline scene by scene. Start with the title as a level-1 heading. Use "
    "dialogue, sensory detail and a strong final image.",
}

# Rules the story writer and the repairer both follow. Prevention is cheaper
# than repair, so the writer sees the same rules the validator enforces.
CANON_RULES = """## Canon rules (must follow)
- Approved material is binding. Do not change any character's motivation, relationship,
  arc, backstory facts (e.g. how someone died), or the approved ending.
- Do not introduce new major characters, organizations, plot devices, threats or deadlines
  that are not in the approved material.
- Every important event needs an on-page cause: if someone is captured, arrested, killed,
  betrayed or arrives somewhere that matters, show or state how.
- Every important object or piece of information (documents, evidence, money, weapons,
  records, secrets) must be shown being obtained before it is used.
- Keep each character's location consistent; a character who dies or is last seen in one
  place cannot later be described in another without explanation.
- Causes come before effects: consequences (arrests, investigations, collapses) happen
  only after the event that triggers them.
- Minor sensory and descriptive details not in the approved material are fine."""


def system_prompt(state: dict) -> str:
    return (
        "You are a senior story developer and screenwriter inside a creative studio tool. "
        f"You are developing {FORMAT_NOTES.get(state.get('content_type'), 'a story')}. "
        f"Genre: {', '.join(state.get('genres', []))}. Tone: {', '.join(state.get('tones', []))}. "
        f"Write ALL output in {state.get('language', 'English')}. "
        "Material the writer has approved is canon: keep names, facts, events and "
        "motivations consistent with it. Output only the requested content in clean "
        "Markdown, with no preamble or commentary."
    )


def validator_system_prompt() -> str:
    return (
        "You are a strict story continuity editor. Your first job is canon fidelity and "
        "logical continuity; prose quality comes second and can never make up for a "
        "continuity failure. You reply with a single JSON object in English, even when "
        "the story is written in another language."
    )


def _brief(state: dict) -> str:
    return (
        "## Writer's brief\n"
        f"- Format: {state.get('content_type')}\n- Idea: {state.get('idea')}\n"
        f"- Genre: {', '.join(state.get('genres', []))}\n"
        f"- Tone: {', '.join(state.get('tones', []))}\n"
        f"- Language: {state.get('language')}\n- Length: {state.get('length')}\n"
    )


def _context(stage: str, state: dict) -> str:
    """Only the approved stages this stage needs (keeps prompts small)."""
    needed = STAGE_CONTEXT.get(stage, [])
    parts = []
    canon = get_approved_canon(state, stages=needed)
    if canon:
        parts.append(format_canon(canon))
    directions = get_writer_directions(state, stages=needed)
    if directions:
        parts.append(
            "### Writer directions (still apply)\n" + format_directions(directions)
        )
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
    if stage in STAGES_WITH_IDEA_ANALYSIS and state.get("idea_analysis"):
        parts.append(
            "## Idea analysis (guidance only, not canon)\n" + state["idea_analysis"]
        )
    if bible := format_bible(state, upto=stage):
        parts.append(
            "## Story Bible (hard facts from approved stages; never contradict)\n"
            + bible
        )
    if context := _context(stage, state):
        parts.append(context)
    if stage == "story":
        parts.append(CANON_RULES)
    if state.get("fix_notes") and state.get(stage):

        parts.append(
            "## Draft to correct\n"
            + state[stage]
            + "\n\n## Consistency problems to fix\n"
            + "\n".join(f"- {n}" for n in state["fix_notes"])
            + "\n\nRewrite the draft so it fixes ONLY these problems and agrees with the "
            "Story Bible. Keep everything else, including format and length."
        )
    # A draft already exists for this stage only when the writer pressed Retry.
    # It is NOT canon: it is shown only so the new version can differ from it.
    elif state.get(stage):
        retry = (
            "## Previous draft (rejected by the writer, NOT canon)\n"
            + state[stage]
            + "\n\nWrite a clearly different version, not a light rephrase."
        )
        if state.get("feedback"):
            retry += f"\nThe writer's direction: {state['feedback']}"
        parts.append(retry)
    parts.append(f"## Your task: {LABELS[stage]}\n{task}")
    return "\n\n".join(parts)


VALIDATION_SCHEMA = {
    "ledger": {
        "characters": [
            "<name>: status changes in order (alive/injured/dead + cause), "
            "locations in order"
        ],
        "objects_and_information": [
            "<item>: where it first appears -> how it is obtained "
            "-> who has it later"
        ],
        "key_events": ["<cause> -> <action> -> <consequence>"],
    },
    "hard_failures": [
        {
            "type": "<one of the hard failure types>",
            "issue": "<what is wrong, in one sentence>",
            "evidence": "<short quote or paraphrase from the story showing it>",
            "fix": "<the smallest change that would fix it>",
        }
    ],
    "warnings": [
        {
            "type": "<motivation|pacing|clarity|prose|other>",
            "issue": "<...>",
            "evidence": "<...>",
            "fix": "<...>",
        }
    ],
    "strengths": ["<...>"],
    "rewrite_notes": ["<one concrete instruction per hard failure, then key warnings>"],
    "score": "<integer 0-100>",
    "status": "<PASS or FAIL>",
}


def validator_prompt(state: dict) -> str:
    canon = get_approved_canon(state, exclude=("story",))
    directions = get_writer_directions(state)
    parts = [
        _brief(state),
        "## APPROVED CANON (authoritative; the story must follow it)\n"
        + (format_canon(canon) or "(none)"),
    ]
    if directions:
        parts.append(
            "## Writer directions (must remain respected)\n"
            + format_directions(directions)
        )
    if bible := format_bible(state):
        parts.append("## Story Bible (hard facts)\n" + bible)
    parts.append("## STORY TO VALIDATE\n" + current_story(state))
    parts.append(
        "## Your task: strict canon and continuity validation\n"
        "Work in this order.\n\n"
        "1. Build a short ledger (max ~12 entries per list) while reading the story:\n"
        "   - every named character's status changes (alive/injured/dead and the stated "
        "cause) and important locations, in story order;\n"
        "   - every plot-important object or piece of information (documents, records, "
        "evidence, money, weapons, vehicles, secrets): where it first appears, how it is "
        "obtained, who has it later;\n"
        "   - key events as CAUSE -> ACTION -> CONSEQUENCE.\n\n"
        "2. Use the ledger to check, in priority order:\n"
        "   a. Canon fidelity: motivations, relationships, arcs, backstory facts, conflict "
        "and the approved ending all match the approved canon. Nothing major was added.\n"
        "   b. Contradictions: the same fact stated two different ways (e.g. two causes of "
        "one death, two places where one character died).\n"
        "   c. Causal continuity: for each important event ask what caused it. If a "
        "character is captured, arrested, killed, rescued or appears somewhere that matters "
        "and the story never shows or states how, that is missing_causal_event.\n"
        "   d. Object and information origin: if a character uses or hands over an "
        "important object or information and the story never shows them obtaining it, that "
        "is missing_object_origin or missing_information_origin.\n"
        "   e. Location continuity: only for plot-important movements or contradictions; "
        "do not demand a travel scene for every move.\n"
        "   f. Temporal order: consequences must not happen, or be described as already "
        "done, before their cause (e.g. an investigation finished before evidence is "
        "handed over).\n"
        "   g. Writer directions: anything the writer asked to remove or change must not "
        "come back (reintroduced_rejected_element).\n"
        "   h. Then prose, emotional development, pacing and escalation.\n\n"
        "3. Classify each problem.\n"
        f"   HARD FAILURE types: {', '.join(HARD_FAILURE_TYPES)}.\n"
        "   Use a hard failure only for real contradictions, canon violations, and missing "
        "causes/origins of plot-important events or items. Unclear emotional motivation, "
        "pacing and style problems are WARNINGS, not hard failures.\n"
        "   Every hard failure must include evidence from the story and the smallest fix.\n"
        "   Do not flag anything that is actually established in the story or the canon.\n\n"
        "4. Score 0-100. If there is any hard failure the score must be 60 or lower and "
        "status must be FAIL, however good the prose is. Beautiful writing never "
        "compensates for a continuity failure.\n\n"
        "Respond with ONLY this JSON object, no code fences, no text before or after:\n"
        + json.dumps(VALIDATION_SCHEMA, indent=2)
    )
    return "\n\n".join(parts)


JSON_RETRY_NOTE = (
    "\n\nIMPORTANT: your previous reply could not be parsed. Reply with ONLY the JSON "
    "object described above: start with { and end with }, no other text."
)


def rewrite_prompt(state: dict) -> str:
    """Minimal repair of the story, driven by the validator's exact findings."""
    canon = get_approved_canon(state, exclude=("story",))
    directions = get_writer_directions(state)
    r = state.get("quality_report", {})

    def lines(items):
        return (
            "\n".join(
                f"- [{i['type']}] {i['issue']}"
                + (f"\n  Evidence: {i['evidence']}" if i.get("evidence") else "")
                + (f"\n  Suggested fix: {i['fix']}" if i.get("fix") else "")
                for i in items
            )
            or "(none)"
        )

    parts = [
        _brief(state),
        "## APPROVED CANON (authoritative)\n" + (format_canon(canon) or "(none)"),
    ]
    if directions:
        parts.append(
            "## Writer directions (must remain respected)\n"
            + format_directions(directions)
        )
    parts += [
        "## CURRENT STORY\n" + current_story(state),
        "## VALIDATION REPORT\n### Hard failures (must all be fixed)\n"
        + lines(r.get("hard_failures", []))
        + "\n\n### Warnings (fix only if a one- or two-sentence change does it)\n"
        + lines(r.get("warnings", []))
        + (
            "\n\n### Rewrite notes\n"
            + "\n".join(f"- {n}" for n in r.get("rewrite_notes", []))
            if r.get("rewrite_notes")
            else ""
        ),
        CANON_RULES,
        "## Your task: minimal repair\n"
        "Repair ONLY the problems listed above, using the smallest necessary correction.\n"
        "- Keep every other sentence exactly as it is.\n"
        "- To fix a missing cause or origin, add a short transition of 1-3 sentences that "
        "uses characters, places and objects already in the canon or the story.\n"
        "- To fix a contradiction, make the story agree with the approved canon. If the "
        "canon is silent, make it agree with the story's first mention.\n"
        "- Never solve a problem by adding a new major character, organization, subplot, "
        "chase, threat or deadline.\n"
        "- Preserve characters, relationships, motivations, central conflict, setting, "
        "approved ending, emotional direction, tone, language, and length (within 10%).\n"
        "Output the complete corrected story only, with no notes or explanations.",
    ]
    return "\n\n".join(parts)


def revise_prompt(state: dict, instruction: str) -> str:
    canon = get_approved_canon(state, exclude=("story",))
    return (
        _brief(state)
        + "\n\n## APPROVED CANON\n"
        + format_canon(canon)
        + "\n\n## Current story\n"
        + state.get("final_story", "")
        + f"\n\n## Your task: Revise\nApply this change from the writer: {instruction}\n"
        "Change only what the instruction requires. Keep everything else, the same language, "
        "the approved characters and the approved ending. Output the full revised story only."
    )


COVERAGE_CHECKS = {
    "beats": "Every character arc listed in the Story Bible has a beat where it pays off, "
    "and the approved ending's key actions appear exactly as approved.",
    "outline": "Every approved beat appears in a scene, and every important event has its "
    "cause shown in an earlier scene.",
}

FACT_RULES = (
    f"Facts: up to {MAX_FACTS_PER_STAGE} short, concrete statements from the draft that "
    "later stages must not contradict: places (which city/town), who lives where, ages, "
    "dates and time frame, past events and their causes, relationships, how things end, "
    "character arcs that must pay off, important objects and where they came from. "
    "One fact per line, no opinions."
)


def check_prompt(stage: str, state: dict) -> str:
    """Cheap consistency check of a new stage draft against the Story Bible."""
    bible = format_bible(state, upto=stage) or "(no approved facts yet)"
    coverage = COVERAGE_CHECKS.get(stage, "")
    return (
        f"## Story Bible (hard facts from approved stages)\n{bible}\n\n"
        f"## New {LABELS[stage]} draft\n{state.get(stage, '')}\n\n"
        "## Your task\n"
        "1. Conflicts: list every place where the draft contradicts the Story Bible, or "
        "contradicts itself (e.g. two causes for one event, one person in two places, "
        "something that happens before its cause, an object or event with no origin)."
        + (f" Also check: {coverage}" if coverage else "")
        + "\n"
        "2. Warnings: important facts that are vague or missing (for example, which city "
        "the story is set in), and anything unrealistic for the setting.\n"
        f"3. {FACT_RULES}\n\n"
        "Only list real problems; an empty list is a good answer. Reply with ONLY this "
        'JSON: {"conflicts": ["..."], "warnings": ["..."], "facts": ["..."]}'
    )


def extract_facts_prompt(stage: str, state: dict) -> str:
    """Facts from a stage the writer edited (their text is canon as written)."""
    return (
        f"## {LABELS[stage]} (approved by the writer)\n{state.get(stage, '')}\n\n"
        f"## Your task\n{FACT_RULES}\n\n"
        'Reply with ONLY this JSON: {"facts": ["..."]}'
    )


def checker_system_prompt() -> str:
    return (
        "You are a meticulous story continuity editor. You compare a new draft against "
        "established facts and report contradictions precisely. You reply with a single "
        "JSON object in English, even when the draft is in another language."
    )
