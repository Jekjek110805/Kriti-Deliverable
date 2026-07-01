#!/usr/bin/env python3
"""
hermes_llm.py - Hermes Agent LLM client for Kriti Content Writer.
Calls the local Hermes agent for content generation.
No LiteLLM/OpenRouter needed — uses the Hermes agent directly.
"""
import subprocess
import os
import re

import shutil
HERMES_BIN = shutil.which("hermes") or "/opt/hermes/bin/hermes"
DEFAULT_MODEL = os.environ.get("HERMES_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")


def _clean_output(text):
    """Strip Hermes UI formatting from output."""
    if not text:
        return ""
    # Remove ANSI escape codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def call_hermes(prompt, model=None, timeout=120):
    """
    Call the Hermes agent CLI with a prompt and return the cleaned response.
    """
    model = model or DEFAULT_MODEL
    cmd = [
        HERMES_BIN,
        "chat",
        "-q",
        prompt,
        "-m",
        model,
        "-Q",  # quiet mode: only final response
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "HOME": "/opt/data", "HERMES_HOME": "/opt/data"},
        )
        if result.returncode != 0:
            # fallback: try without -Q flag
            cmd = [
                HERMES_BIN,
                "chat",
                "-q",
                prompt,
                "-m",
                model,
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "HOME": "/opt/data", "HERMES_HOME": "/opt/data"},
            )
        output = result.stdout.strip()
        return _clean_output(output)
    except subprocess.TimeoutExpired:
        return f"[ERROR] Hermes call timed out after {timeout}s"
    except Exception as e:
        return f"[ERROR] Failed to call Hermes: {e}"


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        print(call_hermes(prompt))
    else:
        print("Usage: python hermes_llm.py <prompt>")
