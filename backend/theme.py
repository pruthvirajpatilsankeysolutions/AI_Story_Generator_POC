"""Gradio theme and custom CSS."""
import gradio as gr

THEME = gr.themes.Soft(
    primary_hue=gr.themes.Color(c50="#FFF8E8", c100="#FFEFC7", c200="#FBDC91",
                                c300="#F2C45A", c400="#E3A72F", c500="#C98A10",
                                c600="#A8720C", c700="#855A0B", c800="#63430A",
                                c900="#442E07", c950="#2A1C04"),
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Work Sans"), "system-ui", "sans-serif"],
)

HEAD = ('<link href="https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700'
        '&display=swap" rel="stylesheet">')

CSS = """
.gradio-container { max-width: 1120px !important; width: 100% !important; margin: 0 auto; }
#studio-title h1 { font-family: 'Courier Prime', monospace; font-size: 2rem; margin: .4rem 0 0; }
#create-card { max-width: 680px; margin: 1.5rem auto 0; }
#dev-screen { width: 100%; }

/* Progress rail */
.rail { list-style: none; padding: 0; margin: 0; }
.rail li { display: flex; gap: .6rem; padding: .42rem .6rem; border-radius: 6px; color: #8A939B; }
.rail li .mark { width: 1.2rem; text-align: center; font-weight: 700; }
.rail li.done { color: #1F2A30; } .rail li.done .mark { color: #2E7D6B; }
.rail li.current { background: #FFF3D6; color: #1F2A30; font-weight: 600; }
.rail li.current .mark { color: #C98A10; }
.rail-head { font-weight: 700; margin-bottom: .4rem; }
.dark .rail li.done, .dark .rail li.current { color: #E8ECEF; }
.dark .rail li.current { background: #3A3120; }

/* Drafts read like a script page */
.draft { font-family: 'Courier Prime', 'Courier New', monospace; line-height: 1.65;
  background: #fff; border: 1px solid #DDE2E5; border-left: 4px solid #C98A10;
  border-radius: 4px; padding: 1.4rem 1.8rem; max-height: 60vh; overflow-y: auto; }
.draft * { font-family: inherit; }
.draft .draft { border: none !important; padding: 0; background: none !important;
  max-height: none; overflow: visible; }
.dark .draft { background: #1E2327; border-color: #384046; }
#edit-box textarea { font-family: 'Courier Prime', 'Courier New', monospace; line-height: 1.6; }
"""