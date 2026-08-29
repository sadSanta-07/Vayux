import os
from typing import Optional


def get_gemini_api_key(value: Optional[str] = None) -> Optional[str]:
    """Return the configured Gemini API key without exposing it in logs."""
    sources = [value, os.getenv("GEMINI_API_KEY"), os.getenv("GOOGLE_API_KEY")]

    for source in sources:
        key = source.strip() if source else ""
        if key:
            return key
    return None


def is_rate_limit_error(error: BaseException) -> bool:
    """Identify Gemini 429 errors across SDK and WebSocket error shapes."""
    for target in (error, getattr(error, "response", None)):
        if target is None:
            continue
        for attribute in ("code", "status_code", "status"):
            value = getattr(target, attribute, None)
            if value == 429 or str(value).strip() == "429":
                return True
            normalized = str(value).upper()
            if any(
                marker in normalized
                for marker in (
                    "RESOURCE_EXHAUSTED",
                    "RATE_LIMIT_EXCEEDED",
                    "QUOTA_EXCEEDED",
                )
            ):
                return True

    message = " ".join(
        str(value)
        for value in (getattr(error, "message", None), str(error))
        if value
    ).upper()
    return any(
        marker in message
        for marker in (
            "RESOURCE_EXHAUSTED",
            "RATE_LIMIT_EXCEEDED",
            "QUOTA_EXCEEDED",
            "429 TOO MANY REQUESTS",
        )
    )
