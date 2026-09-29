import os
import json
from pathlib import Path
import time
from dotenv import load_dotenv
import re
load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

GROQ_MODEL = os.getenv("GROQ_MODEL") or os.getenv("STORY_MODEL") or "openai/gpt-oss-20b"

REASONING_EFFORT = os.getenv("REASONING_EFFORT", "medium")


OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
# Later stages send all accepted material, so the model needs room to remember it.
OLLAMA_CONTEXT = int(os.getenv("OLLAMA_CONTEXT", "16384"))
# Qwen3 "thinks" by default, which is slow on a CPU; turn it off unless asked.
OLLAMA_THINK = os.getenv(
    "OLLAMA_THINK", "false" if OLLAMA_MODEL.startswith("qwen3") else ""
)


REASONING_BUFFER = 4000
MAX_OUTPUT = 65536

_SAMPLE_PATH = Path(__file__).parent / os.getenv(
    "SAMPLE_FILE", "data/sample_story.json"
)
SAMPLE = json.loads(_SAMPLE_PATH.read_text("utf-8"))

_calls: dict[str, int] = {}
_clients: dict = {}


def provider() -> str:
    """Returns 'gemini', 'groq', 'ollama' or 'mock'."""
    choice = os.getenv("LLM_PROVIDER", "").strip().lower()
    if choice == "ollama":
        return "ollama"
    if choice in ("gemini", "groq") and os.getenv(f"{choice.upper()}_API_KEY"):
        return choice
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    return "mock"


def is_mock() -> bool:
    return not os.getenv("GROQ_API_KEY")


def provider_name() -> str:
    return {
        "gemini": f"Gemini ({GEMINI_MODEL})",
        "groq": f"Groq ({GROQ_MODEL})",
        "ollama": f"Ollama, local ({OLLAMA_MODEL})",
    }.get(provider(), "Mock mode (sample text)")


def generate(system: str, prompt: str, max_token: int = 1500, stage="") -> str:
    which = provider()
    if which == "mock":
        value = SAMPLE.get(stage, SAMPLE["story"])
        if isinstance(value, list):
            n = _calls.get(stage, 0)
            _calls[stage] = n + 1
            value = value[min(n, len(value) - 1)]
        return value
    
    limit = min(max_token + REASONING_BUFFER, MAX_OUTPUT)
    call = {"gemini": _gemini, "groq": _groq, "ollama": _ollama}[which]
    text = strip_thinking(call(system, prompt, limit))
    if not text:
        raise RuntimeError(
            "The model returned no text. Its thinking may have used the whole token "
            "budget; raise REASONING_BUFFER in llm.py or lower the thinking level."
        )
    return text


def strip_thinking(text: str) -> str:
    text = text or ""
    text = re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", text, flags=re.DOTALL | re.IGNORECASE)
    closing = re.search(r"</think(?:ing)?>", text, flags=re.IGNORECASE)
    if closing:
        text = text[closing.end():]
    text = re.sub(r"<think(?:ing)?>.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()



def _gemini(system: str, prompt: str, limit: int) -> str:
    from google import genai
    from google.genai import errors, types

    if "gemini" not in _clients:
        _clients["gemini"] = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    config = types.GenerateContentConfig(
        system_instruction=system, max_output_tokens=limit, temperature=0.8
    )

    for attempt in range(4):
        try:
            response = _clients["gemini"].models.generate_content(
                model=GEMINI_MODEL, contents=prompt, config=config
            )
            return (response.text or "").strip()
        except errors.APIError as e:
            if e.code != 429 or attempt == 3:
                raise
            time.sleep(15 * (attempt + 1))  # 15s, 30s, 45s


def _groq(system: str, prompt: str, limit: int) -> str:
    if "groq" not in _clients:
        from groq import Groq

        _clients["groq"] = Groq(max_retries=3, timeout=300)
    response = _clients["groq"].chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_completion_tokens=limit,
        reasoning_effort=REASONING_EFFORT,
        temperature=0.8,
    )
    return (response.choices[0].message.content or "").strip()


def _ollama(system: str, prompt: str, limit: int) -> str:
    if "ollama" not in _clients:
        from ollama import Client

        # Local models are slower than cloud ones; allow up to 20 minutes per stage.
        _clients["ollama"] = Client(host=OLLAMA_HOST, timeout=1200)

    extra = {}
    if OLLAMA_THINK.lower() in ("false", "true"):
        extra["think"] = OLLAMA_THINK.lower() == "true"
    elif OLLAMA_THINK:  # e.g. "low" for gpt-oss models
        extra["think"] = OLLAMA_THINK

    try:
        response = _clients["ollama"].chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            options={
                "num_predict": limit,
                "num_ctx": OLLAMA_CONTEXT,
                "temperature": 0.8,
            },
            
            **extra,
        )
    except ConnectionError as e:
        raise RuntimeError(
            "Can't reach Ollama. Open the Ollama app, then try again."
        ) from e

    return response.message.content or ""