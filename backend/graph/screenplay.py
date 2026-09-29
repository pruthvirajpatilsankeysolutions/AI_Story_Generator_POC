"""Screenplay writer: turns the approved outline + final story into a Fountain script.

A feature script is far too long for one model call, so it is written one scene
at a time. Each scene call sees the Story Bible, the cast, short summaries of all
earlier scenes and the end of the previous scene, which keeps it consistent and
keeps every request small.
"""
import re
from datetime import date

from config import (SCREENPLAY_MAX_SCENES, SCREENPLAY_PAGES,
                    SCREENPLAY_WORDS_PER_PAGE)
from llm import generate

from .canon import _extract_json, format_bible, get_approved_canon

SUMMARY_MARK = "=== SUMMARY ==="
HEADING_RE = re.compile(r"^(INT\./EXT\.|INT/EXT\.?|I/E\.?|INT\.|EXT\.)\s", re.IGNORECASE)

FOUNTAIN_RULES = """## Screenplay format (Fountain), follow exactly
- Start with a scene heading on its own line: INT. or EXT., then LOCATION - DAY or NIGHT,
  all in capitals (e.g. INT. SCHOOL HOMEROOM - NIGHT).
- Action lines: present tense, short paragraphs (1-4 lines), only what the camera can see
  or hear. No thoughts, no backstory explanations, no camera directions unless essential.
- Introduce a character the first time they appear with their NAME IN CAPITALS and age,
  e.g. AARAV (25).
- Dialogue: the character name in CAPITALS on its own line, the dialogue on the next line.
  Parentheticals such as (quietly) go on their own line between the name and the dialogue,
  and only when needed.
- Use (V.O.) for voice-over and (O.S.) for off-screen after the name.
- Transitions (CUT TO:, MATCH CUT TO:) only when they add meaning, on their own line.
- Keep scene headings, character names and action in English. Write DIALOGUE in the
  story's language.
- No markdown, no bold, no bullet points, no scene numbers, no notes."""


def screenplay_system_prompt(state: dict) -> str:
    return (
        "You are a professional screenwriter. You write tight, visual, production-ready "
        "screenplay pages in Fountain format, and you never contradict established story "
        f"facts. Dialogue is written in {state.get('language', 'English')}."
    )


def plan_prompt(state: dict) -> str:
    return (
        "## Approved outline\n" + state.get("outline", "") + "\n\n"
        "## Your task\nConvert this outline into a scene list for a screenplay. Keep the "
        "outline's order and content; do not add or remove story events. Merge tiny "
        f"moments into one scene where natural, up to {SCREENPLAY_MAX_SCENES} scenes.\n"
        "For each scene give: heading (INT. or EXT. + LOCATION + DAY/NIGHT, in capitals, in "
        "English), title (a few words), summary (1-2 sentences of what happens), and "
        "characters (names of who appears).\n"
        'Reply with ONLY this JSON: {"scenes": [{"heading": "...", "title": "...", '
        '"summary": "...", "characters": ["..."]}]}'
    )


def parse_plan(raw: str) -> list[dict]:
    data = _extract_json(raw) or {}
    scenes = []
    for s in data.get("scenes", []) or []:
        if not isinstance(s, dict) or not (s.get("summary") or s.get("title")):
            continue
        heading = str(s.get("heading") or "").strip().upper()
        if not HEADING_RE.match(heading + " "):
            heading = "INT. " + (heading or "LOCATION - DAY")
        scenes.append({
            "heading": heading,
            "title": str(s.get("title") or "").strip(),
            "summary": str(s.get("summary") or "").strip(),
            "characters": [str(c).strip() for c in (s.get("characters") or []) if str(c).strip()],
        })
    return scenes[:SCREENPLAY_MAX_SCENES]


def fallback_plan(outline: str) -> list[dict]:
    """If the model's plan can't be read: one scene per numbered outline line."""
    scenes = []
    for line in outline.splitlines():
        m = re.match(r"\s*\d+[.)]\s*(.+)", line)
        if m:
            text = re.sub(r"\*\*", "", m.group(1)).strip()
            title, _, summary = text.partition(":")
            scenes.append({"heading": "INT. LOCATION - DAY", "title": title.strip(),
                           "summary": (summary or title).strip(), "characters": []})
    return scenes[:SCREENPLAY_MAX_SCENES]


def plan_scenes(state: dict) -> list[dict]:
    raw = generate(screenplay_system_prompt(state), plan_prompt(state), 4000,
                   stage="scene_plan")
    scenes = parse_plan(raw) or fallback_plan(state.get("outline", ""))
    if not scenes:
        raise RuntimeError("Couldn't read any scenes from the approved outline.")
    return scenes


# ---------------------------------------------------------------- one scene
def words_per_scene(state: dict, n_scenes: int) -> int:
    pages = SCREENPLAY_PAGES.get(state.get("length"), SCREENPLAY_PAGES["Medium"])
    words = pages * SCREENPLAY_WORDS_PER_PAGE // max(1, n_scenes)
    return max(150, min(1500, words))


def scene_prompt(state: dict, plan: list[dict], i: int, summaries: list[str],
                 previous_text: str) -> str:
    scene = plan[i]
    cast = get_approved_canon(state, stages=["characters"]).get("characters", "")
    parts = [f"## Story Bible (hard facts; never contradict)\n{format_bible(state) or '(none)'}"]
    if cast:
        parts.append("## Approved characters\n" + cast)
    if summaries:
        parts.append("## What has happened so far (earlier scenes)\n"
                     + "\n".join(f"{n + 1}. {s}" for n, s in enumerate(summaries)))
    if previous_text:
        tail = "\n".join(previous_text.strip().splitlines()[-25:])
        parts.append("## End of the previous scene (for flow; do not repeat it)\n" + tail)
    upcoming = plan[i + 1]["title"] if i + 1 < len(plan) else "(this is the final scene)"
    parts.append(
        f"## Scene to write: {i + 1} of {len(plan)}\n"
        f"Heading: {scene['heading']}\nTitle: {scene['title']}\n"
        f"What happens: {scene['summary']}\n"
        f"Characters: {', '.join(scene['characters']) or 'as needed'}\n"
        f"Next scene: {upcoming}"
    )
    parts.append(FOUNTAIN_RULES)
    parts.append(
        "## Your task\n"
        f"Write ONLY this scene, about {words_per_scene(state, len(plan))} words. Dramatize "
        "exactly what happens in the scene description; do not jump ahead to later scenes "
        "and do not add new major characters or plot events. Every important object or "
        "piece of information used here must already exist in the story so far or be "
        "obtained on-screen in this scene.\n"
        f"After the scene, write a line containing only {SUMMARY_MARK} and then a 1-2 "
        "sentence summary (in English) of what changed in this scene."
    )
    return "\n\n".join(parts)


def split_summary(raw: str) -> tuple[str, str]:
    text = re.sub(r"^```\w*\s*|\s*```$", "", (raw or "").strip())
    if SUMMARY_MARK in text:
        body, summary = text.split(SUMMARY_MARK, 1)
        return body.strip(), " ".join(summary.split())
    return text.strip(), ""


def known_names(state: dict) -> set[str]:
    """Character names from the approved Characters stage (bold names)."""
    cast = state.get("characters", "")
    names = set()
    for m in re.findall(r"\*\*([^*]+)\*\*", cast):
        full = re.split(r"[—\-–(,]", m)[0].strip().upper()
        if full:
            names.add(full)
            names.update(part for part in full.split() if len(part) > 2)
    return names


def check_format(text: str, scene: dict, names: set[str]) -> tuple[str, list[str]]:
    """Code-level checks. Fixes a missing heading; warns about unknown speakers."""
    warnings = []
    lines = text.strip().splitlines()
    first = next((ln for ln in lines if ln.strip()), "")
    if not HEADING_RE.match(first.strip() + " "):
        text = scene["heading"] + "\n\n" + text.strip()
        warnings.append("Scene heading was missing and was added automatically.")

    # Speaker cues: an all-capitals line followed by a non-empty line.
    lines = text.splitlines()
    for n, line in enumerate(lines[:-1]):
        cue = line.strip()
        if (cue and cue == cue.upper() and any(c.isalpha() for c in cue)
                and not HEADING_RE.match(cue + " ") and not cue.endswith("TO:")
                and lines[n + 1].strip() and len(cue) < 40):
            name = re.sub(r"\s*\((V\.O\.|O\.S\.|O\.C\.|CONT'D)\)", "", cue).strip()
            if names and name not in names and not any(p in names for p in name.split()):
                warnings.append(f"New speaking character not in the approved cast: {name}")
    return text, sorted(set(warnings), key=warnings.index)


def write_scene(state: dict, plan: list[dict], i: int, summaries: list[str],
                previous_text: str) -> tuple[str, str, list[str]]:
    target = words_per_scene(state, len(plan))
    raw = generate(screenplay_system_prompt(state),
                   scene_prompt(state, plan, i, summaries, previous_text),
                   min(8000, target * 3 + 800), stage="scene")
    body, summary = split_summary(raw)
    body, warnings = check_format(body, plan[i], known_names(state))
    if not summary:
        summary = plan[i]["summary"]  # fall back to the plan so later scenes stay informed
    return body, summary, warnings


# ---------------------------------------------------------------- assembly
def story_title(state: dict) -> str:
    for line in (state.get("final_story") or "").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Untitled"


def assemble(state: dict, scenes: list[str]) -> str:
    title_page = (
        f"Title: {story_title(state)}\n"
        "Credit: Written by\n"
        "Author: AI Creative Story Studio (draft)\n"
        f"Draft date: {date.today():%d %B %Y}\n"
    )
    return title_page + "\n\n" + "\n\n".join(s.strip() for s in scenes) + "\n\nFADE OUT.\n"