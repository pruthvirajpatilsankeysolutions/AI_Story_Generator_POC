from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from config import CHECKED_STAGES

from . import nodes
from .nodes import NEXT_NODE
from .state import StoryState


def review(state: StoryState) -> Command:
    """Pauses for the writer. Resumes with {"action": accept|edit|retry, ...}.

    accept -> the generated stage becomes approved canon (its facts join the Story Bible)
    edit   -> the writer's edited text becomes approved canon (facts are re-read from it)
    retry  -> regenerate; the stage is NOT canon until accepted
    """
    stage = state["current_stage"]
    decision = interrupt({
        "stage": stage,
        "content": state.get(stage, ""),
        "warnings": state.get("stage_warnings", []),
    })
    action = decision.get("action")
    reset = {"feedback": "", "fix_notes": [], "stage_fix_count": 0, "stage_warnings": []}

    if action == "retry":
        feedback = (decision.get("feedback") or "").strip()
        update = {**reset, "feedback": feedback}
        if feedback:
            directions = dict(state.get("writer_directions", {}) or {})
            directions[stage] = directions.get(stage, []) + [feedback]
            update["writer_directions"] = directions
        return Command(goto=f"gen_{stage}", update=update)

    approved = state.get("approved", [])
    update = {**reset, "approved": approved + ([stage] if stage not in approved else [])}

    if action == "edit":
        update[stage] = decision.get("text", state.get(stage, ""))
        if stage in CHECKED_STAGES:
            return Command(goto="sync_bible", update=update) 
        return Command(goto=NEXT_NODE[stage], update=update)

    # accept
    if stage in CHECKED_STAGES:
        if state.get("draft_facts"):
            bible = dict(state.get("story_bible", {}) or {})
            bible[stage] = state["draft_facts"]
            update.update(story_bible=bible, draft_facts=[])
        else:
            return Command(goto="sync_bible", update=update)  
    return Command(goto=NEXT_NODE[stage], update=update)


def build_graph():
    g = StateGraph(StoryState)
    g.add_node("input_validator", nodes.input_validator)
    g.add_node("idea_analyzer", nodes.idea_analyzer)
    for name, fn in nodes.STAGE_NODES.items():
        g.add_node(name, fn)
        g.add_conditional_edges(name, nodes.route_after_generation, ["check_stage", "review"])

    g.add_node("check_stage", nodes.check_stage,
               destinations=tuple(nodes.STAGE_NODES.keys()) + ("review",))
    g.add_node("review", review,
               destinations=tuple(nodes.STAGE_NODES.keys()) + ("quality_checker", "sync_bible"))
    g.add_node("sync_bible", nodes.sync_bible,
               destinations=tuple(nodes.STAGE_NODES.keys()))
    g.add_node("quality_checker", nodes.quality_checker)
    g.add_node("rewriter", nodes.rewriter)
    g.add_node("finalize", nodes.finalize)

    g.add_edge(START, "input_validator")
    g.add_conditional_edges(
        "input_validator",
        nodes.route_after_validation,
        {"idea_analyzer": "idea_analyzer", "end": END},
    )
    g.add_edge("idea_analyzer", "gen_concept")
    g.add_conditional_edges(
        "quality_checker", nodes.route_after_quality, ["rewriter", "finalize"]
    )

    g.add_edge("rewriter", "quality_checker")
    g.add_edge("finalize", END)

    return g.compile(checkpointer=MemorySaver())