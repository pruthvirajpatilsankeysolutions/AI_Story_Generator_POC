"""AI Creative Story Studio: Gradio UI.

Run:  python app.py
Screens: Create Story → Development (Accept / Edit / Retry) → Final Story + Revise
         → Screenplay (optional)
"""

import tempfile

import gradio as gr

from client import StoryClient
from config import (
    CONTENT_TYPES,
    GENRES,
    LABELS,
    LANGUAGES,
    LENGTHS,
    REVISION_OPTIONS,
    STAGES,
    TONES,
)
from llm import provider_name
from theme import CSS, HEAD, THEME

client = StoryClient()
RAIL = [("idea", "Idea")] + [(s, LABELS[s]) for s in STAGES] + [("polish", "Polish")]


# ---------------------------------------------------------------- render helpers
def rail_html(values: dict, current: str | None, done: bool) -> str:
    approved = set(values.get("approved", []))
    items = []
    for key, label in RAIL:
        if key == "idea":
            cls = "done" if values.get("idea_analysis") else "current"
        elif key == "polish":
            cls = "done" if done else ""
        else:
            cls = "done" if key in approved else "current" if key == current else ""
        mark = {"done": "✓", "current": "●"}.get(cls, "○")
        items.append(f'<li class="{cls}"><span class="mark">{mark}</span>{label}</li>')
    return (
        f'<div class="rail-head">My Story</div><ul class="rail">{"".join(items)}</ul>'
    )


def so_far_md(values: dict) -> str:
    parts = [
        f"### {LABELS[s]}\n{values[s]}"
        for s in STAGES
        if s != "story" and s in values.get("approved", []) and values.get(s)
    ]
    return "\n\n---\n\n".join(parts) or "_Accepted stages collect here._"


def report_md(values: dict) -> str:
    """Story Validation panel: status, score, hard failures, warnings, strengths."""
    r = values.get("quality_report") or {}
    if not r:
        return ""
    history = values.get("quality_history") or []
    status = r.get("status", "–")
    badge = {"PASS": "✅ PASS", "FAIL": "❌ FAIL", "UNVERIFIED": "⚠️ NOT VERIFIED"}.get(
        status, status
    )

    def items(title, entries):
        rows = []
        for e in entries:
            row = f"- **{e.get('type', '').replace('_', ' ')}**: {e.get('issue', '')}"
            if e.get("evidence"):
                row += f"  \n  _Evidence:_ {e['evidence']}"
            rows.append(row)
        return f"**{title}**\n" + "\n".join(rows)

    out = [
        "### Story Validation",
        f"**Status:** {badge}  ·  **Score:** {r.get('score', '–')}/100",
    ]

    first = history[0] if history else {}
    if r.get("rewritten") and first.get("hard_failures"):
        fixed = len(first["hard_failures"])
        out.append(
            f"The first draft had {fixed} continuity "
            f"problem{'s' if fixed != 1 else ''}. The story was repaired while "
            "preserving the approved canon, then validated again."
        )
    if r.get("reverted_to_draft"):
        out.append(
            "The repair introduced new problems, so the original draft was kept."
        )
    if status == "FAIL" and r.get("unresolved"):
        out.append(
            "Some problems remain after repair. Use **Revise** below to fix them, "
            "or start a new story."
        )
    if status == "UNVERIFIED":
        out.append(
            "Continuity could not be verified this time. Read the story carefully "
            "before using it."
        )

    if r.get("hard_failures"):
        out.append(items("Hard failures", r["hard_failures"]))
    if r.get("warnings"):
        out.append(items("Warnings", r["warnings"]))
    if r.get("strengths"):
        out.append("**Strengths**\n" + "\n".join(f"- {s}" for s in r["strengths"]))
    if r.get("rewritten") and first.get("hard_failures"):
        out.append(items("Fixed in repair", first["hard_failures"]))
    if values.get("revisions"):
        out.append("**Your revisions:** " + "; ".join(values["revisions"]))
    return "\n\n".join(out)


def export_screenplay(text: str) -> str:
    f = tempfile.NamedTemporaryFile(
        "w", delete=False, suffix=".fountain", prefix="screenplay_", encoding="utf-8"
    )
    f.write(text)
    f.close()
    return f.name


def export_story(values: dict) -> str:
    parts = [f"# Story Bible\n\n**Idea:** {values.get('idea', '')}"]
    parts += [
        f"## {LABELS[s]}\n\n{values[s]}"
        for s in STAGES
        if s != "story" and values.get(s)
    ]
    parts.append("## Final Story\n\n" + values.get("final_story", ""))
    f = tempfile.NamedTemporaryFile(
        "w", delete=False, suffix=".md", prefix="story_", encoding="utf-8"
    )
    f.write("\n\n".join(parts))
    f.close()
    return f.name


# ---------------------------------------------------------------- UI
with gr.Blocks(title="AI Creative Story Studio") as demo:
    thread = gr.State(None)

    gr.Markdown(
        "# AI Creative Story Studio\nFrom a one-line idea to a finished story, "
        f"one step at a time.  \n<small>Model: {provider_name()}</small>",
        elem_id="studio-title",
    )

    # ---- Screen 1: Create Story
    with gr.Column(elem_id="create-card") as create_screen:
        content_type = gr.Dropdown(
            CONTENT_TYPES, value="Film Story", label="What do you want to create?"
        )
        idea = gr.Textbox(
            label="Your idea",
            lines=3,
            value="A poor forest worker wants to become powerful and earn respect.",
            placeholder="One or two sentences is enough.",
        )
        genres = gr.CheckboxGroup(
            GENRES, value=["Action", "Crime", "Drama"], label="Genre"
        )
        tones = gr.CheckboxGroup(
            TONES, value=["Gritty", "Emotional", "Intense"], label="Tone"
        )
        with gr.Row():
            language = gr.Dropdown(LANGUAGES, value="English", label="Language")
            length = gr.Dropdown(list(LENGTHS), value="Long", label="Story length")
        develop_btn = gr.Button("Develop my story", variant="primary", size="lg")

    # ---- Screen 2: Development (+ final story)
    with gr.Column(visible=False, elem_id="dev-screen") as dev_screen:
        with gr.Row(equal_height=False):
            with gr.Column(scale=1, min_width=200):
                rail = gr.HTML()
                restart_btn = gr.Button("Start a new story", size="sm")
            with gr.Column(scale=4):
                title = gr.Markdown()

                with gr.Column() as review_group:
                    draft = gr.Markdown(elem_classes=["draft"])
                    direction = gr.Textbox(
                        label="Direction for a retry (optional)",
                        placeholder="e.g. make the villain more powerful",
                    )
                    with gr.Row():
                        accept_btn = gr.Button("Accept", variant="primary")
                        edit_btn = gr.Button("Edit")
                        retry_btn = gr.Button("Retry")

                with gr.Column(visible=False) as edit_group:
                    edit_box = gr.Textbox(
                        label="Edit this stage", lines=16, elem_id="edit-box"
                    )
                    with gr.Row():
                        save_btn = gr.Button("Save and continue", variant="primary")
                        cancel_btn = gr.Button("Cancel")

                with gr.Column(visible=False) as final_group:
                    report = gr.Markdown()
                    final_story = gr.Markdown(elem_classes=["draft"])
                    with gr.Accordion("Revise the story", open=True):
                        revision_choice = gr.Radio(
                            REVISION_OPTIONS, label="Quick changes"
                        )
                        revision_custom = gr.Textbox(
                            label="Or describe your own change",
                            placeholder="e.g. make the ending darker",
                        )
                        revise_btn = gr.Button("Apply revision", variant="primary")
                    download = gr.File(label="Download story (.md)")
                    with gr.Accordion("🎬 Screenplay", open=False):
                        gr.Markdown(
                            "Turn the approved outline and final story into a screenplay, "
                            "written scene by scene. If it stops (for example a rate limit), "
                            "click the button again and it continues where it left off."
                        )
                        screenplay_btn = gr.Button("Write screenplay", variant="primary")
                        screenplay_status = gr.Markdown()
                        screenplay_preview = gr.Code(
                            label="Screenplay (Fountain format)",
                            language=None,
                            interactive=False,
                            lines=25,
                            max_lines=40,
                        )
                        screenplay_file = gr.File(
                            label="Download screenplay (.fountain)"
                        )

                with gr.Accordion("Story so far", open=False):
                    so_far = gr.Markdown()

    VIEW = [
        rail,
        title,
        draft,
        direction,
        review_group,
        edit_group,
        final_group,
        report,
        final_story,
        download,
        so_far,
        revision_choice,
        revision_custom,
    ]

    # ---------------------------------------------------------------- handlers
    def view(status: dict) -> dict:
        v, stage, done = status["values"], status["stage"], status["done"]
        out = {
            rail: rail_html(v, stage, done),
            so_far: so_far_md(v),
            direction: "",
            edit_group: gr.update(visible=False),
        }
        if done:
            return out | {
                title: "### Your story is ready",
                review_group: gr.update(visible=False),
                final_group: gr.update(visible=True),
                report: report_md(v),
                final_story: v.get("final_story", ""),
                download: export_story(v),
                revision_choice: None,
                revision_custom: "",
            }
        step = STAGES.index(stage) + 1
        heading = f"### {LABELS[stage]}  \n<small>Step {step} of {len(STAGES)}</small>"
        if status.get("warnings"):
            heading += (
                "\n\n**⚠️ Consistency check** (use Edit or Retry to fix, or Accept "
                "if it's fine):\n" + "\n".join(f"- {w}" for w in status["warnings"])
            )
        return out | {
            title: heading,
            draft: status["content"],
            review_group: gr.update(visible=True),
            final_group: gr.update(visible=False),
        }

    def safe(fn, *args):
        try:
            return fn(*args)
        except gr.Error:
            raise
        except Exception as e:
            raise gr.Error(f"Something went wrong while writing: {e}")

    def open_dev(idea_text):
        if len((idea_text or "").strip()) < 10:
            raise gr.Error("Describe your idea in at least one full sentence.")
        return {
            create_screen: gr.update(visible=False),
            dev_screen: gr.update(visible=True),
            rail: rail_html({}, None, False),
            title: "### Concept",
            draft: "_Reading your idea and developing a concept…_",
            review_group: gr.update(visible=True),
            final_group: gr.update(visible=False),
            edit_group: gr.update(visible=False),
            so_far: "",
        }

    def start(ctype, idea_text, g, t, lang, size):
        brief = {
            "content_type": ctype,
            "idea": idea_text,
            "genres": g,
            "tones": t,
            "language": lang,
            "length": size,
        }
        tid, status = safe(client.start, brief)
        if status["error"]:
            raise gr.Error(status["error"])
        return {thread: tid} | view(status)

    def open_editor(tid):
        return {
            edit_box: client.status(tid)["content"],
            edit_group: gr.update(visible=True),
            review_group: gr.update(visible=False),
        }

    def revise(tid, choice, custom):
        instruction = (custom or "").strip() or choice
        if not instruction:
            gr.Warning("Pick a quick change or describe your own.")
            return {c: gr.skip() for c in VIEW}
        return view(safe(client.revise, tid, instruction))

    def write_screenplay(tid):
        """Writes the screenplay scene by scene, updating the screen after each scene."""
        if not tid:
            raise gr.Error("Start a story first.")
        try:
            for p in client.write_screenplay(tid):
                if not p["done"]:
                    yield {
                        screenplay_status: f"⏳ {p['message']}",
                        screenplay_preview: p["text"],
                        screenplay_file: None,
                    }
                    continue
                msg = f"**✅ {p['message']}**"
                if p.get("warnings"):
                    msg += "\n\n**Check these:**\n" + "\n".join(
                        f"- {w}" for w in p["warnings"]
                    )
                yield {
                    screenplay_status: msg,
                    screenplay_preview: p["text"],
                    screenplay_file: export_screenplay(p["text"]),
                }
        except gr.Error:
            raise
        except Exception as e:
            raise gr.Error(
                f"Screenplay stopped: {e}. Click Write screenplay again to continue."
            )

    develop_btn.click(
        open_dev,
        idea,
        [
            create_screen,
            dev_screen,
            rail,
            title,
            draft,
            review_group,
            final_group,
            edit_group,
            so_far,
        ],
    ).success(
        start, [content_type, idea, genres, tones, language, length], [thread] + VIEW
    )

    accept_btn.click(lambda tid: view(safe(client.accept, tid)), thread, VIEW)
    retry_btn.click(
        lambda tid, d: view(safe(client.retry, tid, d)), [thread, direction], VIEW
    )
    edit_btn.click(open_editor, thread, [edit_box, edit_group, review_group])
    save_btn.click(
        lambda tid, text: view(safe(client.edit, tid, text)), [thread, edit_box], VIEW
    )
    cancel_btn.click(
        lambda: (gr.update(visible=False), gr.update(visible=True)),
        None,
        [edit_group, review_group],
    )
    revise_btn.click(revise, [thread, revision_choice, revision_custom], VIEW)
    screenplay_btn.click(
        write_screenplay,
        thread,
        [screenplay_status, screenplay_preview, screenplay_file],
    )
    restart_btn.click(
        lambda: (None, gr.update(visible=True), gr.update(visible=False), "", "", None),
        None,
        [
            thread,
            create_screen,
            dev_screen,
            screenplay_status,
            screenplay_preview,
            screenplay_file,
        ],
    )


if __name__ == "__main__":
    demo.queue().launch(theme=THEME, css=CSS, head=HEAD)