from langgraph.types import Command

from config import (
    CHECKED_STAGES,
    MAX_FACTS_PER_STAGE,
    MAX_REPAIR_ROUNDS,
    MAX_STAGE_FIXES,
    STAGES,
)
from llm import generate

from .canon import (
    current_story,
    parse_check,
    parse_facts,
    parse_validation_report,
    unverified_report,
)
from .prompts import (
    JSON_RETRY_NOTE,
    MAX_TOKENS,
    analysis_prompt,
    check_prompt,
    checker_system_prompt,
    extract_facts_prompt,
    rewrite_prompt,
    stage_prompt,
    system_prompt,
    validator_prompt,
    validator_system_prompt,
)


def input_validator(state: dict) -> dict:
    idea = (state.get("idea") or "").strip()
    error = ""
    if len(idea) < 10:
        error = "Describe your idea in at least one full sentence."
    elif len(idea) > 2000:
        error = "Keep the idea under 2,000 characters; details come later."

    return {
        "idea": idea,
        "error": error,
        "approved": [],
        "revisions": [],
        "writer_directions": {},
        "repair_attempts": 0,
        "quality_history": [],
        "story_bible": {},
        "draft_facts": [],
        "stage_warnings": [],
        "fix_notes": [],
        "stage_fix_count": 0,
        "genres": state.get("genres") or ["Drama"],
        "tones": state.get("tones") or ["Emotional"],
    }


def idea_analyzer(state: dict) -> dict:
    return {
        "idea_analysis": generate(
            system_prompt(state),
            analysis_prompt(state),
            MAX_TOKENS["analysis"],
            stage="analysis",
        )
    }


def make_stage_node(stage: str):
    def node(state: dict) -> dict:
        text = generate(
            system_prompt(state),
            stage_prompt(stage, state),
            MAX_TOKENS[stage],
            stage=stage,
        )
        # fix_notes are used once, by this generation; clear them afterwards.
        return {stage: text, "current_stage": stage, "feedback": "", "fix_notes": []}

    node.__name__ = f"gen_{stage}"
    return node


STAGE_NODES = {f"gen_{s}": make_stage_node(s) for s in STAGES}

NEXT_NODE = {
    s: (f"gen_{STAGES[i + 1]}" if i + 1 < len(STAGES) else "quality_checker")
    for i, s in enumerate(STAGES)
}


def route_after_generation(state: dict) -> str:
    """Planning stages are checked before the writer sees them; the story goes to review."""
    return "check_stage" if state.get("current_stage") in CHECKED_STAGES else "review"


def check_stage(state: dict) -> Command:
    """Compare the new draft with the Story Bible before the writer sees it.

    Conflicts -> one automatic fix, then check again.
    Still conflicting (or only warnings) -> show the draft with warnings.
    """
    stage = state["current_stage"]
    raw = generate(
        checker_system_prompt(),
        check_prompt(stage, state),
        MAX_TOKENS["check"],
        stage="check",
    )
    result = parse_check(raw)
    if result is None:  # checker reply unreadable: don't block the writer
        return Command(
            goto="review",
            update={
                "draft_facts": [],
                "stage_warnings": [
                    "The automatic consistency check could not run for this "
                    "stage. Read it carefully before accepting."
                ],
            },
        )

    fixes_used = state.get("stage_fix_count", 0)
    if result["conflicts"] and fixes_used < MAX_STAGE_FIXES:
        return Command(
            goto=f"gen_{stage}",
            update={
                "fix_notes": result["conflicts"],
                "stage_fix_count": fixes_used + 1,
            },
        )

    warnings = [f"Conflict: {c}" for c in result["conflicts"]] + result["warnings"]
    return Command(
        goto="review",
        update={
            "draft_facts": result["facts"][:MAX_FACTS_PER_STAGE],
            "stage_warnings": warnings,
        },
    )


def sync_bible(state: dict) -> Command:
    """After an Edit (or an Accept with no facts yet), re-read the approved text."""
    stage = state["current_stage"]
    raw = generate(
        checker_system_prompt(),
        extract_facts_prompt(stage, state),
        MAX_TOKENS["extract"],
        stage="extract",
    )
    bible = dict(state.get("story_bible", {}) or {})
    bible[stage] = parse_facts(raw)[:MAX_FACTS_PER_STAGE]
    return Command(
        goto=NEXT_NODE[stage], update={"story_bible": bible, "draft_facts": []}
    )


def quality_checker(state: dict) -> dict:
    """Strict canon + continuity validation of the current story version.

    Runs on the first draft and again after every repair. The report is stored in
    quality_report; the story itself is never changed here.
    """
    prompt = validator_prompt(state)
    raw = generate(
        validator_system_prompt(), prompt, MAX_TOKENS["quality"], stage="quality"
    )
    report = parse_validation_report(raw)

    if report is None:  # invalid JSON: ask once more, strictly
        raw = generate(
            validator_system_prompt(),
            prompt + JSON_RETRY_NOTE,
            MAX_TOKENS["quality"],
            stage="quality",
        )
        report = parse_validation_report(raw)

    if (
        report is None
    ):  # still unreadable: fail safely, don't pass and don't rewrite blindly
        report = unverified_report(
            "The validator's reply could not be read, so continuity was not verified."
        )

    attempts = state.get("repair_attempts", 0)
    report["round"] = attempts  # 0 = first draft, 1 = after first repair, ...
    report["version"] = "repaired" if attempts else "draft"
    history = state.get("quality_history", []) + [report]
    return {"quality_report": report, "quality_history": history}


def rewriter(state: dict) -> dict:
    """Minimal repair of exactly what the validator reported. Re-validated afterwards."""
    text = generate(
        system_prompt(state),
        rewrite_prompt(state),
        MAX_TOKENS["rewrite"],
        stage="rewrite",
    )
    return {
        "final_story": text or current_story(state),
        "repair_attempts": state.get("repair_attempts", 0) + 1,
    }


def finalize(state: dict) -> dict:
    report = dict(state.get("quality_report", {}))
    history = state.get("quality_history", [])
    final = current_story(state)

    if (
        len(history) >= 2
        and report.get("status") == "FAIL"
        and len(report.get("hard_failures", []))
        > len(history[0].get("hard_failures", []))
    ):
        final = state.get("story", final)
        report = dict(history[0], reverted_to_draft=True)

    report["unresolved"] = report.get("status") == "FAIL"
    report["rewritten"] = state.get("repair_attempts", 0) > 0
    return {"final_story": final, "quality_report": report, "current_stage": "done"}


def route_after_validation(state: dict) -> str:
    return "end" if state.get("error") else "idea_analyzer"


def route_after_quality(state: dict) -> str:
    report = state.get("quality_report", {})
    status = report.get("status")

    if status == "PASS" and not report.get("hard_failures"):
        return "finalize"
    if status == "UNVERIFIED":
        return "finalize"
    if state.get("repair_attempts", 0) < MAX_REPAIR_ROUNDS:
        return "rewriter"
    return "finalize"
