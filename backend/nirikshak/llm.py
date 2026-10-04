"""LLM provider layer: local Ollama (default) or Google Gemini (for the hosted demo).

Every model call in the app goes through `chat_json` (structured JSON output) or
`vision_text` (read text from an image), so switching provider is one setting:

    NIRIKSHAK_PROVIDER=ollama   # default: qwen2.5:7b + gemma3:4b on the local GPU
    NIRIKSHAK_PROVIDER=gemini   # GEMINI_API_KEY required; key stays on the server
"""
from __future__ import annotations

import json
import os
import random
import time

import httpx

from .config import HI_MODEL, LLM_MODEL, OLLAMA_URL

PROVIDER = os.environ.get("NIRIKSHAK_PROVIDER", "ollama").lower()
GEMINI_MODEL = os.environ.get("NIRIKSHAK_GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


class LLMError(RuntimeError):
    pass


def model_label() -> str:
    return f"{GEMINI_MODEL} (Google Gemini)" if PROVIDER == "gemini" else f"{LLM_MODEL} + {HI_MODEL}"


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


# ---------------- Gemini ----------------

def _gemini_post(body: dict) -> dict:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise LLMError("GEMINI_API_KEY is not set on the server.")
    for attempt in range(6):
        try:
            r = httpx.post(GEMINI_URL, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=180)
        except httpx.HTTPError as e:
            if attempt == 5:
                raise LLMError(f"Gemini request failed: {e}") from e
            time.sleep(2 ** attempt)
            continue
        if r.status_code in (429, 500, 502, 503, 504):  # rate limit / overload: back off and retry
            time.sleep(min(30, 2 ** attempt * 2) + random.random())
            continue
        if r.status_code >= 400:
            raise LLMError(f"Gemini error {r.status_code}: {r.text[:300]}")
        return r.json()
    raise LLMError("Gemini is busy (rate limit). Please try again in a minute.")


def _clean_schema(schema: dict) -> dict:
    """Gemini's JSON-schema support is a subset: drop numeric bounds it may reject."""
    if isinstance(schema, dict):
        return {k: _clean_schema(v) for k, v in schema.items() if k not in ("minimum", "maximum")}
    if isinstance(schema, list):
        return [_clean_schema(x) for x in schema]
    return schema


def _gemini_chat(messages: list[dict], schema: dict, num_predict: int) -> dict:
    body = {
        "model": GEMINI_MODEL,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max(num_predict * 2, 1024),
        "reasoning_effort": "none",
        "response_format": {"type": "json_schema", "json_schema": {"name": "result", "schema": _clean_schema(schema)}},
    }
    data = _gemini_post(body)
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError):
        return {}
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


# ---------------- public API ----------------

def chat_json(messages: list[dict], schema: dict, num_predict: int = 1500, model: str = LLM_MODEL) -> dict:
    if PROVIDER == "gemini":
        return _gemini_chat(messages, schema, num_predict)
    return _ollama_chat(messages, schema, num_predict, model)


def vision_text(image_b64: str, prompt: str) -> str:
    if PROVIDER == "gemini":
        data = _gemini_post({
            "model": GEMINI_MODEL, "temperature": 0, "reasoning_effort": "none", "max_tokens": 3000,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            ]}],
        })
        try:
            return (data["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError):
            return ""
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
