
import gradio as gr

# ------------------------------------------------------------- options
CONTENT_TYPES = ["Film Story", "Short Story", "Web Series Pilot", "Novel Chapter"]
GENRES = ["Action", "Crime", "Drama", "Thriller", "Romance", "Sci-Fi", "Horror", "Comedy"]
TONES = ["Gritty", "Emotional", "Intense", "Dark", "Hopeful", "Satirical"]
LANGUAGES = ["English", "Hindi", "Tamil", "Telugu", "Malayalam", "Kannada", "Spanish", "French"]
LENGTHS = ["Short", "Medium", "Long"]

STAGES = ["Concept", "Logline", "Characters", "Conflict", "Ending",
          "Structure", "Beats", "Outline", "Story"]

SAMPLE = {
    "Concept": "A poor forest worker enters an illegal timber network, first as a loader, "
               "then as the only man who can move logs past the checkposts. Every rung he "
               "climbs costs a piece of the forest he grew up in.",
    "Logline": "When a humiliated forest labourer is pulled into a timber-smuggling ring, he "
               "must outwit a ruthless syndicate boss before the forest he loves is stripped bare.",
    "Characters": "**Raghu** - forest labourer, wants respect\n\n"
                  "**Bhairav** - syndicate boss, wants control\n\n"
                  "**Lakshmi** - Raghu's mother, wants him safe",
    "Conflict": "**External:** Raghu vs the syndicate.\n\n"
                "**Internal:** hunger for respect vs love for the forest.\n\n"
                "**Ticking clock:** the monsoon closes the roads in 30 days.",
    "Ending": "Raghu takes over the syndicate, then burns the final shipment himself. "
              "Final image: a sapling in the ash as the monsoon arrives.",
    "Structure": "**Act 1** - Humiliation and the first run.\n\n"
                 "**Act 2** - Rise, betrayal, the midpoint checkpost.\n\n"
                 "**Act 3** - War with Bhairav and the final choice.",
    "Beats": "1. **Opening Image** - Raghu carrying logs he'll never own.\n"
             "2. **Catalyst** - a public beating.\n"
             "3. **Midpoint** - he runs the checkpost.\n"
             "4. **All Is Lost** - his mother's house burns.\n"
             "5. **Final Image** - a sapling in the ash.",
    "Outline": "1. **Dawn loading** - Raghu is mocked at the depot.\n"
               "2. **The offer** - a smuggler recruits him.\n"
               "3. **The run** - he bluffs past the guards.\n"
               "4. **Fire** - he burns the last shipment.",
    "Story": "# The Last Stand of Teak\n\nThe depot bell rings before the birds wake. "
             "Raghu shoulders a log older than his grandfather...",
}


def fake_generate(stage: str, attempt: int) -> str:
    """Placeholder for the AI. `attempt` > 0 means the user pressed Retry."""
    text = SAMPLE[stage]
    return text if attempt == 0 else f"*Alternative version {attempt}*\n\n{text}"


# ------------------------------------------------------------- styling
CSS = """
.gradio-container { max-width: 1120px !important; width: 100% !important; margin: 0 auto; }
#studio-title h1 { font-family: 'Courier Prime', monospace; font-size: 2rem; margin: .4rem 0 0; }
#dev-screen { width: 100%; }
#create-card { max-width: 680px; margin: 1.5rem auto 0; }
.rail { list-style: none; padding: 0; margin: 0; }
.rail li { display: flex; gap: .6rem; padding: .42rem .6rem; border-radius: 6px; color: #8A939B; }
.rail li .mark { width: 1.2rem; text-align: center; font-weight: 700; }
.rail li.done { color: #1F2A30; } .rail li.done .mark { color: #2E7D6B; }
.rail li.current { background: #FFF3D6; color: #1F2A30; font-weight: 600; }
.rail li.current .mark { color: #C98A10; }
.rail-head { font-weight: 700; margin-bottom: .4rem; }
.draft { font-family: 'Courier Prime', 'Courier New', monospace; line-height: 1.65;
  background: #fff; border: 1px solid #DDE2E5; border-left: 4px solid #C98A10;
  border-radius: 4px; padding: 1.4rem 1.8rem; max-height: 60vh; overflow-y: auto; }
.draft * { font-family: inherit; }
.draft .draft { border: none !important; padding: 0; background: none !important; max-height: none; }
.dark .draft { background: #1E2327; border-color: #384046; }
.dark .rail li.done, .dark .rail li.current { color: #E8ECEF; }
.dark .rail li.current { background: #3A3120; }
"""
HEAD = ('<link href="https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700'
        '&display=swap" rel="stylesheet">')


def rail_html(step: int) -> str:
    rows = [("Idea", "done")]
    rows += [(s, "done" if i < step else "current" if i == step else "")
             for i, s in enumerate(STAGES)]
    items = "".join(
        f'<li class="{c}"><span class="mark">{"✓" if c == "done" else "●" if c else "○"}'
        f'</span>{label}</li>' for label, c in rows)
    return f'<div class="rail-head">My Story</div><ul class="rail">{items}</ul>'


# ------------------------------------------------------------- UI
with gr.Blocks(title="AI Creative Story Studio") as demo:
    # session: current step, retry count, accepted text per stage
    session = gr.State({"step": 0, "attempt": 0, "accepted": {}})

    gr.Markdown("# AI Creative Story Studio\nFrom a one-line idea to a finished story, "
                "one step at a time.", elem_id="studio-title")

    # ---- Screen 1: Create Story
    with gr.Column(elem_id="create-card") as create_screen:
        gr.Dropdown(CONTENT_TYPES, value="Film Story", label="What do you want to create?")
        idea = gr.Textbox(label="Your idea", lines=3,
                          value="A poor forest worker wants to become powerful and earn respect.")
        gr.CheckboxGroup(GENRES, value=["Action", "Crime", "Drama"], label="Genre")
        gr.CheckboxGroup(TONES, value=["Gritty", "Emotional", "Intense"], label="Tone")
        with gr.Row():
            gr.Dropdown(LANGUAGES, value="English", label="Language")
            gr.Dropdown(LENGTHS, value="Long", label="Story length")
        develop_btn = gr.Button("Develop my story", variant="primary", size="lg")

    # ---- Screen 2: Development
    with gr.Column(visible=False, elem_id="dev-screen") as dev_screen:
        with gr.Row(equal_height=False):
            with gr.Column(scale=1, min_width=200):
                rail = gr.HTML()
                restart_btn = gr.Button("Start a new story", size="sm")
            with gr.Column(scale=4):
                title = gr.Markdown()
                with gr.Column() as review_box:
                    draft = gr.Markdown(elem_classes=["draft"])
                    direction = gr.Textbox(label="Direction for a retry (optional)",
                                           placeholder="e.g. make the antagonist a woman")
                    with gr.Row():
                        accept_btn = gr.Button("Accept", variant="primary")
                        edit_btn = gr.Button("Edit")
                        retry_btn = gr.Button("Retry")
                with gr.Column(visible=False) as edit_box_col:
                    edit_box = gr.Textbox(label="Edit this stage", lines=14)
                    with gr.Row():
                        save_btn = gr.Button("Save and continue", variant="primary")
                        cancel_btn = gr.Button("Cancel")
                with gr.Column(visible=False) as final_box:
                    final_story = gr.Markdown(elem_classes=["draft"])

    SCREEN = [rail, title, draft, direction, review_box, edit_box_col, final_box, final_story]

    def show(s):
        """Render the development screen for the current step."""
        step = s["step"]
        if step >= len(STAGES):  # finished
            return [rail_html(step), "### Your story is ready", "", "",
                    gr.update(visible=False), gr.update(visible=False),
                    gr.update(visible=True), s["accepted"]["Story"]]
        stage = STAGES[step]
        return [rail_html(step), f"### {stage}  \n<small>Step {step + 1} of {len(STAGES)}</small>",
                fake_generate(stage, s["attempt"]), "",
                gr.update(visible=True), gr.update(visible=False),
                gr.update(visible=False), ""]

    def develop(idea_text):
        if len(idea_text.strip()) < 10:
            raise gr.Error("Describe your idea in at least one full sentence.")
        s = {"step": 0, "attempt": 0, "accepted": {}}
        return [s, gr.update(visible=False), gr.update(visible=True)] + show(s)

    def accept(s, text=None):
        stage = STAGES[s["step"]]
        s["accepted"][stage] = text if text is not None else fake_generate(stage, s["attempt"])
        s["step"] += 1
        s["attempt"] = 0
        return [s] + show(s)

    def retry(s):
        s["attempt"] += 1
        return [s] + show(s)

    def open_edit(s):
        return (fake_generate(STAGES[s["step"]], s["attempt"]),
                gr.update(visible=True), gr.update(visible=False))

    develop_btn.click(develop, idea, [session, create_screen, dev_screen] + SCREEN)
    accept_btn.click(accept, session, [session] + SCREEN)
    retry_btn.click(retry, session, [session] + SCREEN)
    edit_btn.click(open_edit, session, [edit_box, edit_box_col, review_box])
    save_btn.click(accept, [session, edit_box], [session] + SCREEN)
    cancel_btn.click(lambda: (gr.update(visible=False), gr.update(visible=True)),
                     None, [edit_box_col, review_box])
    restart_btn.click(lambda: (gr.update(visible=True), gr.update(visible=False)),
                      None, [create_screen, dev_screen])

if __name__ == "__main__":
    theme = gr.themes.Soft(
        primary_hue=gr.themes.Color(c50="#FFF8E8", c100="#FFEFC7", c200="#FBDC91",
                                    c300="#F2C45A", c400="#E3A72F", c500="#C98A10",
                                    c600="#A8720C", c700="#855A0B", c800="#63430A",
                                    c900="#442E07", c950="#2A1C04"),
        neutral_hue="slate",
        font=[gr.themes.GoogleFont("Work Sans"), "system-ui", "sans-serif"],
    )
    demo.launch(theme=theme, css=CSS, head=HEAD)