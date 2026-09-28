import uuid

from langgraph.types import Command

from graph.prompts import MAX_TOKENS, revise_prompt, system_prompt
from graph.workflow import build_graph
from llm import generate


class StoryClient:
    def __init__(self):
        self.graph = build_graph()

    @staticmethod
    def _cfg(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    def start(self, brief: dict) -> tuple[str, dict]:
        thread_id = str(uuid.uuid4())
        self.graph.invoke(brief, self._cfg(thread_id))
        return thread_id, self.status(thread_id)

    def accept(self, thread_id: str) -> dict:
        return self._resume(thread_id, {"action": "accept"})

    def edit(self, thread_id: str, text: str) -> dict:
        return self._resume(thread_id, {"action": "edit", "text": text})

    def retry(self, thread_id: str, feedback: str = "") -> dict:
        return self._resume(thread_id, {"action": "retry", "feedback": feedback})

    def revise(self, thread_id: str, instruction: str) -> dict:
        """Revise the finished story without re-running the pipeline."""
        values = self.graph.get_state(self._cfg(thread_id)).values
        text = generate(system_prompt(values), revise_prompt(values, instruction),
                        MAX_TOKENS["revise"], stage="revise")
        self.graph.update_state(self._cfg(thread_id), {
            "final_story": text, "revisions": values.get("revisions", []) + [instruction]})
        return self.status(thread_id)

    def status(self, thread_id: str) -> dict:
        snap = self.graph.get_state(self._cfg(thread_id))
        pending = next((t.interrupts[0].value for t in snap.tasks if t.interrupts), None)
        return {
            "values": snap.values,
            "stage": pending["stage"] if pending else None,
            "content": pending["content"] if pending else "",
            "done": not snap.next and not snap.values.get("error"),
            "error": snap.values.get("error", ""),
        }

    def _resume(self, thread_id: str, decision: dict) -> dict:
        self.graph.invoke(Command(resume=decision), self._cfg(thread_id))
        return self.status(thread_id)