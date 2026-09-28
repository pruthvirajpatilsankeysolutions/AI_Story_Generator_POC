from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


from config import STAGES

from . import nodes
from .state import StoryState

NEXT_NODE = {
    s: (f"gen_{STAGES[i + 1]}" if i + 1 < len(STAGES) else "quality_checker")
    for i, s in enumerate(STAGES)
}


def review(state: StoryState) -> Command:
    """Pauses for the writer. Resumes with {"action": accept|edit|retry, ...}."""
    stage = state["current_stage"]
    decision = interrupt({"stage": stage, "content": state.get(stage, "")})
    action = decision.get("action")

    if action == "retry":
        return Command(
            goto=f"gen_{stage}", update={"feedback": decision.get("feedback", "")}
        )

    update = {"approved": state.get("approved", []) + [stage], "feedback": ""}
    if action == "edit":
        update[stage] = decision.get("text", state.get(stage, ""))
    return Command(goto=NEXT_NODE[stage], update=update)


def build_graph():
    g = StateGraph(StoryState)
    g.add_node("input_validator", nodes.input_validator)
    g.add_node("idea_analyzer", nodes.idea_analyzer)
    for name, fn in nodes.STAGE_NODES.items():
        g.add_node(name, fn)

    g.add_node(
        "review",
        review,
        destinations=(tuple(nodes.STAGE_NODES.keys()) + ("quality_checker",)),
    )
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

    g.add_edge("rewriter", "finalize")
    g.add_edge("finalize", END)

    return g.compile(checkpointer=MemorySaver())
