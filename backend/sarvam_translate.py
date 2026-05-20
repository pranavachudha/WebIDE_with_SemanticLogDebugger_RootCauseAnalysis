import os
from typing import Any

import httpx


# Paste your Sarvam API key here if you do not want to use an environment variable.
# Example: SARVAM_API_KEY = "sk_your_key_here"
SARVAM_API_KEY = "sk_80iyktp5_OFQUoMwi14VePstfDsxmec7K"

SARVAM_API_URL = "https://api.sarvam.ai/translate"
SARVAM_TRANSLATE_MODEL = "sarvam-translate:v1"


def translate_text(text: str, target_language_code: str) -> dict[str, Any]:
    api_key = os.getenv("SARVAM_API_KEY") or SARVAM_API_KEY
    if not api_key:
        raise ValueError(
            "Sarvam API key is missing. Add it to backend/sarvam_translate.py "
            "or set the SARVAM_API_KEY environment variable."
        )

    if not text.strip():
        raise ValueError("No text was provided for translation.")

    payload = {
        "input": text[:2000],
        "source_language_code": "en-IN",
        "target_language_code": target_language_code,
        "mode": "formal",
        "model": SARVAM_TRANSLATE_MODEL,
        "enable_preprocessing": True,
        "numerals_format": "international",
    }

    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30) as client:
        response = client.post(SARVAM_API_URL, json=payload, headers=headers)

    if response.status_code >= 400:
        raise RuntimeError(f"Sarvam translation failed: {response.text}")

    data = response.json()
    return {
        "translated_text": data.get("translated_text", ""),
        "source_language_code": data.get("source_language_code", "en-IN"),
        "target_language_code": target_language_code,
        "request_id": data.get("request_id"),
    }
