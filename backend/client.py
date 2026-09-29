import uuid

from langgraph.types import Command
from graph import screenplay
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
        text = generate(
            system_prompt(values),
            revise_prompt(values, instruction),
            MAX_TOKENS["revise"],
            stage="revise",
        )
        self.graph.update_state(
            self._cfg(thread_id),
            {
                "final_story": text,
                "revisions": values.get("revisions", []) + [instruction],
            },
        )
        return self.status(thread_id)

    def write_screenplay(self, thread_id: str, restart: bool = False):
        """Write the screenplay scene by scene. Yields progress after every scene.

        Progress is saved after each scene, so if a call fails (for example a rate
        limit), pressing the button again continues from the next unfinished scene.
        """
        cfg = self._cfg(thread_id)
        values = self.graph.get_state(cfg).values
        if not values.get("final_story"):
            raise RuntimeError("Finish the story before writing the screenplay.")

        if restart or values.get("screenplay"):  # finished before: start fresh
            values = {
                **values,
                "screenplay_plan": [],
                "screenplay_scenes": [],
                "scene_summaries": [],
                "screenplay_warnings": [],
                "screenplay": "",
            }

        plan = values.get("screenplay_plan") or []
        if not plan:
            yield {
                "done": False,
                "scene": 0,
                "total": 0,
                "text": "",
                "message": "Planning scenes from the approved outline...",
            }
            plan = screenplay.plan_scenes(values)
        scenes = list(values.get("screenplay_scenes") or [])
        summaries = list(values.get("scene_summaries") or [])
        warnings = list(values.get("screenplay_warnings") or [])
        self.graph.update_state(
            cfg,
            {
                "screenplay_plan": plan,
                "screenplay_scenes": scenes,
                "scene_summaries": summaries,
                "screenplay_warnings": warnings,
                "screenplay": "",
            },
        )

        for i in range(len(scenes), len(plan)):
            yield {
                "done": False,
                "scene": i + 1,
                "total": len(plan),
                "text": "\n\n".join(scenes),
                "message": f"Writing scene {i + 1} of {len(plan)}: {plan[i]['title']}",
            }
            body, summary, scene_warnings = screenplay.write_scene(
                values, plan, i, summaries, scenes[-1] if scenes else ""
            )
            scenes.append(body)
            summaries.append(summary)
            warnings += [f"Scene {i + 1}: {w}" for w in scene_warnings]
            self.graph.update_state(
                cfg,
                {
                    "screenplay_scenes": scenes,
                    "scene_summaries": summaries,
                    "screenplay_warnings": warnings,
                },
            )

        script = screenplay.assemble(values, scenes)
        self.graph.update_state(cfg, {"screenplay": script})
        yield {
            "done": True,
            "scene": len(plan),
            "total": len(plan),
            "text": script,
            "warnings": warnings,
            "message": f"Screenplay ready: {len(plan)} scenes.",
        }

    def status(self, thread_id: str) -> dict:
        snap = self.graph.get_state(self._cfg(thread_id))
        pending = next(
            (t.interrupts[0].value for t in snap.tasks if t.interrupts), None
        )
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
