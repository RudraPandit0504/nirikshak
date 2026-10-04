"""LLM provider layer: local Ollama (default) or free cloud APIs (for the hosted demo).

Every model call in the app goes through `chat_json` (structured JSON output) or
`vision_text` (read text from an image), so switching provider is one setting:

    NIRIKSHAK_PROVIDER=ollama   # default: qwen2.5:7b + gemma3:4b on the local GPU
    NIRIKSHAK_PROVIDER=cloud    # AWS_BEARER_TOKEN_BEDROCK, GROQ_API_KEY and/or GEMINI_API_KEY; keys stay on the server

In cloud mode every model of every configured provider is tried in order, so a rate limit or an
outage on one (each has its own free quota) falls through to the next.
"""
from __future__ import annotations

import json
import os
import random
import re
import time

import logging

import httpx

from .config import HI_MODEL, LLM_MODEL, OLLAMA_URL

log = logging.getLogger("nirikshak.llm")
USED: dict[str, int] = {}  # which cloud model answered, for logs and evals
PROVIDER = os.environ.get("NIRIKSHAK_PROVIDER", "ollama").lower()
if PROVIDER in ("gemini", "groq"):
    PROVIDER = "cloud"


def _models(var: str, default: str) -> list[str]:
    return [m.strip() for m in os.environ.get(var, default).split(",") if m.strip()]


# (name, endpoint, key env var, text models, vision models). All are OpenAI-compatible.
_REGION = os.environ.get("AWS_REGION", "us-east-1")
CLOUD = [
    ("bedrock", f"https://bedrock-runtime.{_REGION}.amazonaws.com/openai/v1/chat/completions", "AWS_BEARER_TOKEN_BEDROCK",
     _models("NIRIKSHAK_BEDROCK_MODELS", "openai.gpt-oss-120b-1:0"),
     _models("NIRIKSHAK_BEDROCK_VISION", "")),
    ("groq", "https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY",
     _models("NIRIKSHAK_GROQ_MODELS", "openai/gpt-oss-120b"),
     _models("NIRIKSHAK_GROQ_VISION", "")),  # Groq has no vision model now; Gemini reads screenshots
    ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "GEMINI_API_KEY",
     _models("NIRIKSHAK_GEMINI_MODELS", "gemini-3.8-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-3.5-flash,gemini-2.5-flash"),
     _models("NIRIKSHAK_GEMINI_VISION", "gemini-3.8-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite")),
]


# Bedrock first when configured (paid from AWS credits, no tight free limits), then Groq (fast,
# ~1000 requests/day per model); when Groq asks us to wait (8k tokens/min free limit),
# move straight on to Gemini, whose free models have small daily quotas but each its own.
ORDER = _models("NIRIKSHAK_CLOUD_ORDER", "bedrock,groq,gemini")


def _available() -> list[tuple]:
    return sorted((c for c in CLOUD if os.environ.get(c[2]) and c[0] in ORDER), key=lambda c: ORDER.index(c[0]))


class LLMError(RuntimeError):
    pass


def model_label() -> str:
    if PROVIDER != "cloud":
        return f"{LLM_MODEL} + {HI_MODEL}"
    avail = _available()
    if not avail:
        return "no API key set"
    # Short label for the header badge: the first model, without provider prefixes or versions.
    m = avail[0][3][0].split("/")[-1].removeprefix("openai.").split(":")[0].removesuffix("-1")
    return f"{m} · {avail[0][0].capitalize()}"


# ---------------- Ollama ----------------

def _ollama_chat(messages: list[dict], schema: dict, num_predict: int, model: str) -> dict:
    try:
        r = httpx.post(f"{OLLAMA_URL}/api/chat", json={
            "model": model, "messages": messages, "format": schema, "stream": False,
            "keep_alive": "10m", "think": False,
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": num_predict},
        }, timeout=300)
    except httpx.ConnectError as e:
        raise LLMError(f"Cannot reach Ollama at {OLLAMA_URL}. Is it running?") from e
    if r.status_code == 404:
        raise LLMError(f"Model {model} not found. Run: ollama pull {model}")
    r.raise_for_status()
    try:
        return json.loads(r.json()["message"]["content"])
    except (KeyError, json.JSONDecodeError):
        return {}


# ---------------- cloud (OpenAI-compatible) ----------------

def _body(provider: str, model: str, base: dict, schema: dict | None) -> dict:
    """Adapt one request to what each provider/model accepts."""
    body = {**base, "model": model}
    msgs = list(base["messages"])
    if provider == "gemini":
        body["reasoning_effort"] = "none"
    elif "gpt-oss" in model:  # Groq and Bedrock
        body["reasoning_effort"] = "low"
    elif "qwen3" in model:
        body["reasoning_effort"] = "none"
    if schema is not None:
        if provider == "gemini" or (provider == "groq" and "gpt-oss" in model):
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "result", "schema": _clean_schema(schema)}}
        else:  # plain JSON mode (Bedrock ignores json_schema): spell the schema out in the prompt
            body["response_format"] = {"type": "json_object"}
            msgs = [*msgs[:-1], {**msgs[-1], "content": f"{msgs[-1]['content']}\n\nReply with only a JSON object matching "
                                                      f"this JSON schema:\n{json.dumps(_clean_schema(schema))}"}]
    body["messages"] = msgs
    return body


def _cloud_post(base: dict, schema: dict | None = None, vision: bool = False) -> dict:
    """Try every configured provider/model in order; back off on rate limits and overloads."""
    chain = [(name, url, key, m) for name, url, key, text, vis in _available() for m in (vis if vision else text)]
    if not chain:
        raise LLMError("No cloud API key is set on the server (AWS_BEARER_TOKEN_BEDROCK, GROQ_API_KEY or GEMINI_API_KEY).")
    last = ""
    for name, url, key, model in chain:
        for attempt in range(2):
            try:
                r = httpx.post(url, json=_body(name, model, base, schema),
                               headers={"Authorization": f"Bearer {os.environ[key]}"}, timeout=120)
            except httpx.HTTPError as e:
                last = f"{name}: {e}"
                time.sleep(1 + attempt)
                continue
            if r.status_code in (429, 500, 502, 503, 504):  # rate limit / overload: retry once, then next model
                last = f"{name} {model}: {r.status_code}"
                try:
                    wait = float(r.headers.get("retry-after", 0))
                except ValueError:
                    wait = 0
                if wait > 6:  # long wait (e.g. daily quota): don't block the user, try the next model now
                    log.warning("%s, retry-after %.0fs: next model", last, wait)
                    break
                log.warning("%s, retrying", last)
                time.sleep(2 + 3 * attempt + random.random())
                continue
            if r.status_code >= 400:  # unknown/retired model, unsupported option, bad key: next model
                last = f"{name} {model}: {r.status_code} {r.text[:200]}"
                log.warning("skipping %s", last)
                break
            USED[f"{name}/{model}"] = USED.get(f"{name}/{model}", 0) + 1
            return r.json()
    raise LLMError(f"The AI service is busy right now ({last}). Please try again in a minute.")


def _clean_schema(schema: dict) -> dict:
    """Drop numeric bounds some providers reject in JSON schemas."""
    if isinstance(schema, dict):
        return {k: _clean_schema(v) for k, v in schema.items() if k not in ("minimum", "maximum")}
    if isinstance(schema, list):
        return [_clean_schema(x) for x in schema]
    return schema


def _content(data: dict) -> str:
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError):
        return ""
    # Bedrock's gpt-oss returns its reasoning inline: "<reasoning>…</reasoning>answer".
    return re.sub(r"(?s)<reasoning>.*?</reasoning>", "", text).strip()


def _cloud_chat(messages: list[dict], schema: dict, num_predict: int) -> dict:
    data = _cloud_post({"messages": messages, "temperature": 0, "max_tokens": max(num_predict, 1024)}, schema)
    return _first_object(_content(data), schema)


def _first_object(text: str, schema: dict) -> dict:
    """The first JSON object in `text` that has the schema's required keys.

    Tolerates fences, bold markers, a sentence around the object, and stray leading braces
    (Bedrock's gpt-oss sometimes emits `{ {"claims": …}`)."""
    want = set(schema.get("required", []))
    dec = json.JSONDecoder()
    fallback: dict = {}
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(text, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            if want <= obj.keys():
                return obj
            fallback = fallback or obj
    return fallback


# ---------------- public API ----------------

def chat_json(messages: list[dict], schema: dict, num_predict: int = 1500, model: str = LLM_MODEL) -> dict:
    if PROVIDER == "cloud":
        return _cloud_chat(messages, schema, num_predict)
    return _ollama_chat(messages, schema, num_predict, model)


def vision_text(image_b64: str, prompt: str) -> str:
    if PROVIDER == "cloud":
        return _content(_cloud_post({"temperature": 0, "max_tokens": 3000, "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
        ]}]}, vision=True))
    try:
        r = httpx.post(f"{OLLAMA_URL}/api/chat", json={
            "model": HI_MODEL, "stream": False,
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 1500},
            "messages": [{"role": "user", "content": prompt, "images": [image_b64]}],
        }, timeout=300)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise LLMError(f"Could not read the image: {e}") from e
    return r.json().get("message", {}).get("content", "").strip()


def unload_local_models() -> None:
    """Free GPU memory before Whisper (Ollama keeps models loaded). Nothing to do for Gemini."""
    if PROVIDER != "ollama":
        return
    for m in {LLM_MODEL, HI_MODEL}:
        try:
            httpx.post(f"{OLLAMA_URL}/api/generate", json={"model": m, "keep_alive": 0}, timeout=30)
        except httpx.HTTPError:
            pass
