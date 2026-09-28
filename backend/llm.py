import os
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("GROQ_MODEL") or os.getenv("STORY_MODEL") or "openai/gpt-oss-20b"

REASONING_EFFORT = os.getenv("REASONING_EFFORT", "medium")
REASONING_BUFFER = 4000
MAX_OUTPUT = 65536

_SAMPLE_PATH = Path(__file__).parent / os.getenv(
    "SAMPLE_FILE", "data/sample_story.json"
)
SAMPLE = json.loads(_SAMPLE_PATH.read_text("utf-8"))

_calls: dict[str, int] = {}
_client = None


def is_mock() -> bool:
    return not os.getenv("ANTHROPIC_API_KEY")


def provider_name() -> str:
    return "Mock mode (sample text)" if is_mock() else f"Groq ({MODEL})"


def generate(system: str, prompt: str, max_token: int = 1500, stage="") -> str:
    if is_mock:
        value = SAMPLE.get(stage, "Sample text.")
        if isinstance(value, list):
            n = _calls.get(stage, 0)
            _calls[stage] = n + 1
            value = value[min(n, len(value) - 1)]
        return value

    global _client
    if _client is None:
        from groq import Groq

        _client = Groq(max_retries=3, timeout=300)

    response = _client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_completion_tokens=min(max_token + REASONING_BUFFER, MAX_OUTPUT),
        reasoning_effort=REASONING_EFFORT,
        temperature=0.8,
    )

    choice = response.choices[0]
    text = (choice.message.content or "").strip()
    if not text and choice.finish_reason == "length":

        raise RuntimeError(
            "The model used its whole token budget on reasoning. "
            "Set REASONING_EFFORT=low or raise REASONING_BUFFER in llm.py."
        )

    return text
