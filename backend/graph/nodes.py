from email.mime import text
import json
from config import REWRITE_THRESHOLD, STAGES
from llm import generate
import re
from .prompts import (
    MAX_TOKENS,
    analysis_prompt,
    quality_prompt,
    rewrite_prompt,
    stage_prompt,
    system_prompt,
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
        return {stage: text, "current_stage": stage, "feedback": ""}

    node.__name__ = f"gen_{stage}"
    return node


STAGE_NODES = {f"gen_{s}": make_stage_node(s) for s in STAGES}


def quality_checker(state: dict) -> dict:
    raw = generate(
        system_prompt(state),
        quality_prompt(state),
        MAX_TOKENS["quality"],
        stage="quality",
    )
    return {"quality_report": parse_report(raw)}


def rewriter(state: dict) -> dict:
    text = generate(
        system_prompt(state),
        rewrite_prompt(state),
        MAX_TOKENS["rewrite"],
        stage="rewrite",
    )
    return {
        "final_story": text,
        "quality_report": dict(state.get("quality_report", {}), rewritten=True),
    }


def finalize(state: dict) -> dict:
    return {
        "final_story": state.get("final_story") or state.get("story", ""),
        "current_stage": "done",
    }


def route_after_validation(state: dict) -> str:
    return "end" if state.get("error") else "idea_analyzer"


def route_after_quality(state: dict) -> str:
    score = state.get("quality_report", {}).get("score", 0)
    return "finalize" if score >= REWRITE_THRESHOLD else "rewriter"


def parse_report(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        data = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        data = {}
    return {
        "score": int(data.get("score", 0) or 0),
        "strengths": list(data.get("strengths", [])),
        "issues": list(data.get("issues", []))
        or ([] if data else ["Report could not be read."]),
        "rewrite_notes": data.get("rewrite_notes", ""),
    }
