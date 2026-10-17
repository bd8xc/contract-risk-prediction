"""Small shared Groq client used by the agents under this workspace."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

DEFAULT_MODEL = "openai/gpt-oss-20b"
DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"


class GroqError(RuntimeError):
    """Missing credentials or a failed Groq API request."""


def groq_is_configured() -> bool:
    key = os.getenv("GROQ_API_KEY", "").strip()
    return bool(key and not key.lower().startswith(("put_your", "your_", "replace_me")))


def _settings() -> tuple[str, str]:
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_is_configured():
        raise GroqError("Set GROQ_API_KEY in the Sem7 .env file")
    base_url = os.getenv("GROQ_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    return key, f"{base_url}/chat/completions"


def groq_chat_completion(
    prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.1,
    json_mode: bool = False,
    timeout: float = 120,
) -> str:
    api_key, endpoint = _settings()
    body: dict[str, Any] = {
        "model": model or os.getenv("GROQ_MODEL", DEFAULT_MODEL),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=timeout,
        )
        if not response.ok:
            try:
                detail = response.json().get("error", {}).get("message", "")
            except (ValueError, AttributeError):
                detail = ""
            suffix = f": {detail}" if detail else ""
            raise GroqError(f"Groq returned HTTP {response.status_code}{suffix}")
        content = response.json()["choices"][0]["message"]["content"]
    except GroqError:
        raise
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
        raise GroqError(f"Groq request failed ({type(exc).__name__})") from exc
    if not isinstance(content, str) or not content.strip():
        raise GroqError("Groq returned an empty response")
    return content.strip()


def groq_model_available(model: str | None = None, *, timeout: float = 10) -> bool:
    try:
        api_key, endpoint = _settings()
        base_url = endpoint.removesuffix("/chat/completions")
        response = requests.get(
            f"{base_url}/models/{model or os.getenv('GROQ_MODEL', DEFAULT_MODEL)}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        return response.ok
    except (GroqError, requests.RequestException):
        return False
