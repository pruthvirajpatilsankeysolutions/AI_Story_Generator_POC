"""Approved canon and validation-report helpers.

Canon = the content of stages the writer ACCEPTED or EDITED. Drafts that are
waiting for review, and drafts the writer retried, are never canon.
"""

import json
import re

from config import HARD_FAILURE_TYPES, LABELS, REWRITE_THRESHOLD, STAGES



def get_approved_canon(state: dict, stages=None, exclude=()) -> dict:
    """Return {stage: content} for approved stages only, in story order.

    stages:  limit to these stages (e.g. the context a generation stage needs).
    exclude: leave these out (e.g. "story" when the story itself is being checked).
    """
    approved = set(state.get("approved", []))
    wanted = STAGES if stages is None else [s for s in STAGES if s in stages]
    return {
        s: state[s]
        for s in wanted
        if s in approved and s not in exclude and state.get(s)
    }


def get_writer_directions(state: dict, stages=None) -> list[str]:
    """Retry directions for approved stages. They are constraints once approved."""
    approved = set(state.get("approved", []))
    directions = state.get("writer_directions", {}) or {}
    out = []
    for s in STAGES:
        if s in approved and (stages is None or s in stages):
            out += [f"({LABELS[s]}) {d}" for d in directions.get(s, [])]
    return out


def format_canon(canon: dict, heading: str = "Approved") -> str:
    return "\n\n".join(
        f"### {heading} {LABELS[s]}\n{text}" for s, text in canon.items()
    )


def format_directions(directions: list[str]) -> str:
    return "\n".join(f"- {d}" for d in directions)


def current_story(state: dict) -> str:
    """The version being validated: the repaired story if one exists, else the draft."""
    return state.get("final_story") or state.get("story", "")


# ---------------------------------------------------------------- report parsing
def _extract_json(raw: str):
    """Pull the first JSON object out of a model reply (handles ``` fences and chatter)."""
    if not raw:
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _items(value, default_type: str) -> list[dict]:
    """Normalize a list of problems into [{type, issue, evidence, fix}]."""
    if not value:
        return []
    if not isinstance(value, list):
        value = [value]
    out = []
    for item in value:
        if isinstance(item, str):
            item = {"type": default_type, "issue": item}
        if not isinstance(item, dict):
            continue
        issue = str(item.get("issue") or item.get("description") or "").strip()
        if not issue:
            continue
        out.append(
            {
                "type": str(item.get("type") or default_type).strip(),
                "issue": issue,
                "evidence": str(item.get("evidence") or "").strip(),
                "fix": str(item.get("fix") or item.get("suggested_fix") or "").strip(),
            }
        )
    return out


def _strings(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [
            line.strip("-• ").strip() for line in value.splitlines() if line.strip()
        ]
    return [str(v).strip() for v in value if str(v).strip()]


def parse_validation_report(raw: str):
    """Turn the validator's reply into a safe report dict, or None if unreadable.

    The PASS/FAIL status is decided HERE, in code, not trusted from the model:
    any hard failure means FAIL, whatever score the model gave.
    """
    data = _extract_json(raw)
    if data is None:
        return None

    try:
        score = int(float(data.get("score", 0) or 0))
    except (TypeError, ValueError):
        score = 0
    if 0 < score <= 10:  # tolerate the old 1-10 scale
        score *= 10
    score = max(0, min(100, score))

    hard = _items(data.get("hard_failures"), "other")
    for item in hard:  # unknown types still count as hard failures
        if item["type"] not in HARD_FAILURE_TYPES:
            item["type"] = "other"
    warnings = _items(data.get("warnings"), "warning")
    model_status = str(data.get("status", "")).strip().upper()

    if hard or model_status == "FAIL" or score < REWRITE_THRESHOLD:
        status = "FAIL"
    else:
        status = "PASS"

    return {
        "status": status,
        "score": score,
        "hard_failures": hard,
        "warnings": warnings,
        "strengths": _strings(data.get("strengths")),
        "rewrite_notes": _strings(data.get("rewrite_notes")),
        # Kept for older code that reads report["issues"].
        "issues": [h["issue"] for h in hard] + [w["issue"] for w in warnings],
    }


def unverified_report(reason: str) -> dict:
    """Used when the validator's reply can't be read even after a retry.

    The story is NOT marked PASS and is NOT blindly rewritten; the UI tells
    the writer that validation could not be completed.
    """
    return {
        "status": "UNVERIFIED",
        "score": 0,
        "hard_failures": [],
        "warnings": [
            {"type": "validator_error", "issue": reason, "evidence": "", "fix": ""}
        ],
        "strengths": [],
        "rewrite_notes": [],
        "issues": [reason],
    }


# ---------------------------------------------------------------- story bible
BIBLE_ORDER = [
    "concept",
    "logline",
    "characters",
    "conflict",
    "ending",
    "structure",
    "beats",
    "outline",
]


def format_bible(state: dict, upto: str | None = None) -> str:
    """The Story Bible as a compact fact list, from approved stages only.

    upto: stop before this stage (a stage never sees its own old facts).
    """
    bible = state.get("story_bible", {}) or {}
    approved = set(state.get("approved", []))
    lines = []
    for s in BIBLE_ORDER:
        if s == upto:
            break
        if s in approved:
            lines += [f"- {fact}" for fact in bible.get(s, [])]
    return "\n".join(lines)


def parse_check(raw: str):
    """Read the per-stage checker's reply: {conflicts, warnings, facts}. None if unreadable."""
    data = _extract_json(raw)
    if data is None:
        return None
    return {
        "conflicts": _strings(data.get("conflicts")),
        "warnings": _strings(data.get("warnings")),
        "facts": _strings(data.get("facts")),
    }


def parse_facts(raw: str) -> list[str]:
    """Read a facts-only reply (used after the writer edits a stage)."""
    data = _extract_json(raw)
    return _strings(data.get("facts")) if data else []
