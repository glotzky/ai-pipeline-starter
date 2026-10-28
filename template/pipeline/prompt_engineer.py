"""Optional prompt-engineer stage: turn the spec into a short brief so the developer (Devin, billed in ACUs) explores less.

Backends (repository variable PIPELINE_PROMPT_ENGINEER):
  off     (default) nothing runs; the built-in developer prompt is used
  claude  the `prompt-engineer` agent runs through the Claude CLI (a small, cheap model)
  ollama  a local or hosted Ollama server (OLLAMA_HOST, default http://localhost:11434; OLLAMA_MODEL): no API cost
  openai  any OpenAI-compatible endpoint (PIPELINE_PE_URL, PIPELINE_PE_MODEL, optional PIPELINE_PE_API_KEY): LM Studio,
          vLLM, or a hosted provider (some have free tiers; check their current terms)

The brief only ever ADDS guidance. The fixed rules in the developer prompt (no PR, no secrets, tests required, stay on the
branch) stay in code and are never taken from model output. Any failure falls back to the built-in prompt: this stage never
fails a run.
"""
import json
import os
import re
import urllib.request

BACKENDS = ("off", "claude", "ollama", "openai")
MIN_CHARS, MAX_CHARS = 120, 6000
SECTION_WORDS = ("goal", "files", "tests", "done when")


def backend(env=None):
    raw = ((env if env is not None else os.environ).get("PIPELINE_PROMPT_ENGINEER", "off") or "off").strip().lower()
    return raw if raw in BACKENDS else "off"


def build_input(spec, design):
    parts = ["IMPLEMENTATION SPEC:\n" + spec.strip()]
    if design and design.strip():
        parts.append("DESIGN BRIEF:\n" + design.strip())
    return "\n\n".join(parts)


def validate(text):
    """Return the cleaned brief, or None if it does not look like one. Rejecting is always safe: the fallback is the default prompt."""
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"^```(?:markdown|md)?\n|\n```$", "", text).strip()
    if not (MIN_CHARS <= len(text) <= MAX_CHARS):
        return None
    low = text.lower()
    if sum(1 for w in SECTION_WORDS if w in low) < 3 or "test" not in low:
        return None
    return text


def _post(url, payload, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # raises on HTTP errors and timeouts
        return json.loads(resp.read().decode())


def _ollama(system, user, env):
    host = (env.get("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
    if "://" not in host:
        host = "http://" + host
    data = _post(f"{host}/api/generate", {
        "model": env.get("OLLAMA_MODEL") or "llama3.2:3b", "system": system, "prompt": user, "stream": False,
        "options": {"temperature": 0.2}}, {}, int(env.get("PIPELINE_PE_TIMEOUT") or "600"))
    return data.get("response", "")


def _openai(system, user, env):
    url = (env.get("PIPELINE_PE_URL") or "").rstrip("/")
    if not url:
        raise RuntimeError("PIPELINE_PE_URL is not set")
    headers = {"Authorization": f"Bearer {env['PIPELINE_PE_API_KEY']}"} if env.get("PIPELINE_PE_API_KEY") else {}
    data = _post(f"{url}/chat/completions", {
        "model": env.get("PIPELINE_PE_MODEL") or "", "temperature": 0.2,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
        headers, int(env.get("PIPELINE_PE_TIMEOUT") or "600"))
    return data["choices"][0]["message"]["content"]


def generate(kind, system, spec, design, env=None, claude_stage=None, brief_path=None):
    """Return (brief_or_None, status). status: ok | invalid | unavailable | off. Never raises."""
    env = env if env is not None else os.environ
    if kind == "off":
        return None, "off"
    try:
        if kind == "claude":
            if claude_stage is None:
                return None, "unavailable"
            claude_stage("prompt-engineer", "Write the brief for the spec in .pipeline/spec.md "
                         "(and .pipeline/design.md if it exists) to .pipeline/devin-brief.md.", max_turns=10)
            text = brief_path.read_text() if brief_path and brief_path.exists() else ""
        elif kind == "ollama":
            text = _ollama(system, build_input(spec, design), env)
        else:
            text = _openai(system, build_input(spec, design), env)
    except Exception as e:  # noqa: BLE001 (any failure means: use the default prompt)
        print(f"[prompt-engineer] {kind} unavailable, using the default developer prompt: {type(e).__name__}", flush=True)
        return None, "unavailable"
    brief = validate(text)
    return (brief, "ok") if brief else (None, "invalid")
