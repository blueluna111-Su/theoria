"""Minimal Gemini REST client (no SDK — only `requests`, to avoid SDK churn).

Exposes generate_json(): send a system+user prompt, ask for application/json,
parse and return a dict. Retries on transient errors / rate limits.
"""
from __future__ import annotations

import json
import os
import time

import requests

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.5-flash"


class GeminiError(RuntimeError):
    pass


def generate_json(
    system: str,
    prompt: str,
    *,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.5,
    max_output_tokens: int = 8192,
    retries: int = 4,
    throttle_sec: float = 2.0,
) -> dict:
    """Call Gemini and return the parsed JSON object from the response."""
    api_key = api_key or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise GeminiError("GOOGLE_API_KEY not set")

    url = f"{API_BASE}/{model}:generateContent?key={api_key}"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
            "responseMimeType": "application/json",
        },
    }

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, json=body, timeout=120)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise GeminiError(f"transient HTTP {resp.status_code}: {resp.text[:300]}")
            resp.raise_for_status()
            data = resp.json()
            cand = (data.get("candidates") or [{}])[0]
            parts = cand.get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts).strip()
            if not text:
                raise GeminiError(f"empty response: {json.dumps(data)[:300]}")
            return json.loads(text)
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < retries:
                wait = throttle_sec * attempt
                print(f"  ! Gemini attempt {attempt} failed ({e}); retrying in {wait:.0f}s")
                time.sleep(wait)
    raise GeminiError(f"failed after {retries} attempts: {last_err}")
