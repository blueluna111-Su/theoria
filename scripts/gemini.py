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
# Primary model + a lighter fallback used only if the primary stays overloaded.
DEFAULT_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]


class GeminiError(RuntimeError):
    pass


class _Permanent(GeminiError):
    """Non-retryable error (bad request / auth) — don't waste retries on it."""


def _call_once(url: str, body: dict) -> dict:
    resp = requests.post(url, json=body, timeout=120)
    if resp.status_code in (400, 401, 403, 404):
        raise _Permanent(f"HTTP {resp.status_code}: {resp.text[:300]}")
    if resp.status_code == 429 or resp.status_code >= 500:
        raise GeminiError(f"transient HTTP {resp.status_code}: {resp.text[:200]}")
    resp.raise_for_status()
    data = resp.json()
    cand = (data.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", [])).strip()
    if not text:
        raise GeminiError(f"empty response: {json.dumps(data)[:300]}")
    return json.loads(text)


def generate_json(
    system: str,
    prompt: str,
    *,
    api_key: str | None = None,
    model: str | list[str] = DEFAULT_MODELS,
    temperature: float = 0.5,
    max_output_tokens: int = 8192,
    retries: int = 5,
    throttle_sec: float = 3.0,
) -> dict:
    """Call Gemini and return the parsed JSON. Retries transient 429/5xx with
    exponential backoff (capped), then falls back to the next model in the list."""
    api_key = api_key or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise GeminiError("GOOGLE_API_KEY not set")

    models = [model] if isinstance(model, str) else list(model)
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
    for mi, m in enumerate(models):
        url = f"{API_BASE}/{m}:generateContent?key={api_key}"
        for attempt in range(1, retries + 1):
            try:
                return _call_once(url, body)
            except _Permanent:
                raise
            except Exception as e:  # noqa: BLE001  (transient / parse)
                last_err = e
                if attempt < retries:
                    wait = min(throttle_sec * (2 ** (attempt - 1)), 30)
                    print(f"  ! [{m}] attempt {attempt} failed ({e}); retrying in {wait:.0f}s")
                    time.sleep(wait)
        if mi < len(models) - 1:
            print(f"  ! [{m}] exhausted; falling back to {models[mi + 1]}")
    raise GeminiError(f"failed on all models {models}: {last_err}")
