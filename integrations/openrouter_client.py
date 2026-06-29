"""
OpenRouter client for Kriti (OpenAI-compatible chat completions).

Used by the Hermes engine to optionally run LLM-driven Stage 1A analysis with
the configured model (e.g. owl-alpha). When not configured, the caller falls
back to the deterministic engine — analysis never hard-fails on a missing key.

Configuration (environment variables):
  OPENROUTER_API_KEY    required to enable LLM analysis
  OPENROUTER_MODEL      model slug, default "owl-alpha"
  OPENROUTER_BASE_URL   default "https://openrouter.ai/api/v1"
  OPENROUTER_KEY_FILE   optional path to a file containing the key
"""
import json
import os
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "owl-alpha"


class OpenRouterError(Exception):
    """Raised when an OpenRouter request cannot be completed."""


class OpenRouterClient:
    def __init__(self):
        self.base_url = os.getenv("OPENROUTER_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        self.model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
        self.api_key = self._load_key()

    def _load_key(self):
        key = os.getenv("OPENROUTER_API_KEY", "")
        if key:
            return key
        key_file = os.getenv("OPENROUTER_KEY_FILE", "")
        if key_file and os.path.exists(key_file):
            with open(key_file, encoding="utf-8") as f:
                return f.read().strip()
        return ""

    def is_configured(self):
        return bool(self.base_url and self.api_key)

    def status(self):
        return {
            "configured": self.is_configured(),
            "base_url": self.base_url,
            "model": self.model,
            "has_api_key": bool(self.api_key),
        }

    def chat(self, messages, temperature=0.2, max_tokens=700, json_mode=False):
        if not self.is_configured():
            raise OpenRouterError("OpenRouter not configured (set OPENROUTER_API_KEY).")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        body = json.dumps(payload).encode()
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            # Optional attribution headers recommended by OpenRouter.
            "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "https://kriti.local"),
            "X-Title": os.getenv("OPENROUTER_TITLE", "Kriti Stage 1A"),
        }
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:300]
            raise OpenRouterError(f"OpenRouter HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as e:
            raise OpenRouterError(f"OpenRouter request failed: {e}") from e

    def chat_json(self, messages, temperature=0.2, max_tokens=700):
        """Call chat and parse a JSON object from the response."""
        raw = self.chat(messages, temperature=temperature, max_tokens=max_tokens, json_mode=True)
        return _parse_json_object(raw)


def _parse_json_object(text):
    """Best-effort extraction of a JSON object from a model response."""
    if not text:
        raise OpenRouterError("Empty model response")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError as e:
            raise OpenRouterError(f"Model did not return valid JSON: {e}") from e
    raise OpenRouterError("Model did not return a JSON object")
