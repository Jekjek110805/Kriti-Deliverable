#!/usr/bin/env python3
"""
OpenRouter-backed LLM client for the Kriti Content Writer.

The public helper is still named hermes_generate() because app/api.py already
imports that name. Internally, generation calls OpenRouter's NVIDIA Nemotron 3
Super model over plain HTTPS — no local binary required, so it works the same
whether the backend runs on the server or on a local machine.
"""
import os
from typing import Optional

import requests
from dotenv import load_dotenv


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

OPENROUTER_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL") or os.getenv("HERMES_MODEL") or "nvidia/nemotron-3-super-120b-a12b:free"
APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "Kriti Content Writer")
APP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost:8000")


def _load_api_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if key:
        return key

    key_file = os.getenv("OPENROUTER_KEY_FILE", "").strip()
    if key_file and os.path.exists(key_file):
        with open(key_file, encoding="utf-8") as f:
            return f.read().strip()

    return ""


def _clean_output(text: Optional[str]) -> str:
    if not text:
        return ""

    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    return cleaned


def hermes_generate(prompt, model=None, max_tokens=900):
    """Generate text with OpenRouter (NVIDIA Nemotron 3 Super) and return plain content."""
    api_key = _load_api_key()
    if not api_key:
        return "[OpenRouter not configured: set OPENROUTER_API_KEY in .env]"

    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Kriti's SEO content writer. Write original, useful, "
                    "natural content. Do not include placeholders or meta-commentary."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": APP_REFERER,
        "X-Title": APP_TITLE,
    }

    try:
        response = requests.post(
            f"{OPENROUTER_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=120,
        )
        if response.status_code >= 400:
            detail = response.text[:300] if response.text else response.reason
            return f"[OpenRouter error {response.status_code}: {detail}]"

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        cleaned = _clean_output(content)
        return cleaned if cleaned else "[OpenRouter returned empty response]"

    except requests.Timeout:
        return "[OpenRouter timeout: request took too long]"
    except Exception as exc:
        return f"[OpenRouter exception: {exc}]"
