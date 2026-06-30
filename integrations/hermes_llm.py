#!/usr/bin/env python3
"""
hermes_llm.py - Hermes Agent LLM client for Kriti Content Writer.
Calls the local Hermes agent (owl-alpha model) for content generation.
No LiteLLM/OpenRouter needed — uses the Hermes agent directly.
"""
import subprocess
import os
import re

HERMES_BIN = "/opt/hermes/bin/hermes"
DEFAULT_MODEL = os.environ.get("HERMES_MODEL", "owl-alpha")


def _clean_output(text):
    """Strip Hermes UI formatting from output."""
    if not text:
        return ""
    # Remove ANSI escape codes
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    # Remove box-drawing characters
    text = re.sub(r'[╭╮╰╯│─├┤┬┴┼╌╍═╎╏║╔╗╚╝]', '', text)
    # Remove the "Hermes" header/footer lines
    text = re.sub(r'⚕ Hermes[─]+', '', text)
    text = re.sub(r'[─]{10,}', '', text)
    # Remove resume/session info
    text = re.sub(r'Resume this session with:.*', '', text, flags=re.DOTALL)
    text = re.sub(r'Session:.*', '', text)
    text = re.sub(r'Duration:.*', '', text)
    text = re.sub(r'Messages:.*', '', text)
    # Remove "Query:" and "Initializing" lines
    text = re.sub(r'^Query:.*\n', '', text)
    text = re.sub(r'^Initializing agent.*\n', '', text)
    # Remove leading/trailing whitespace and blank lines
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    return '\n'.join(lines).strip()


def hermes_generate(prompt, model=None, max_tokens=500):
    """Call Hermes agent with a prompt and return the response text."""
    if not os.path.exists(HERMES_BIN):
        return "[Hermes agent not found at /opt/hermes/bin/hermes]"

    cmd = [
        HERMES_BIN, "chat", "-q", prompt,
        "-m", model or DEFAULT_MODEL,
        "-Q",  # quiet mode
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout
        if result.returncode != 0:
            err = result.stderr[:200] if result.stderr else "Unknown error"
            return f"[Hermes error: {err}]"

        cleaned = _clean_output(output)
        return cleaned if cleaned else "[Hermes returned empty response]"

    except subprocess.TimeoutExpired:
        return "[Hermes timeout — request took too long]"
    except Exception as e:
        return f"[Hermes exception: {e}]"
