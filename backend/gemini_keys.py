import os
from typing import Optional


def get_gemini_api_keys(value: Optional[str] = None) -> list[str]:
    """Return unique Gemini API keys without ever exposing them in logs."""
    sources = [value, os.getenv("GEMINI_API_KEY"), os.getenv("GOOGLE_API_KEY")]

    keys: list[str] = []
    for source in sources:
        if not source:
            continue
        for candidate in source.split(","):
            key = candidate.strip()
            if key and key not in keys:
                keys.append(key)
        if keys:
            break
    return keys


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


class GeminiKeyRing:
    """Tracks the active key and advances only for rate-limit failures."""

    def __init__(self, keys: list[str]):
        if not keys:
            raise ValueError("At least one Gemini API key is required.")
        self._keys = tuple(keys)
        self._index = 0

    @property
    def current(self) -> str:
        return self._keys[self._index]

    @property
    def position(self) -> int:
        return self._index + 1

    @property
    def size(self) -> int:
        return len(self._keys)

    def advance_for(self, error: BaseException) -> bool:
        if not is_rate_limit_error(error) or self._index >= len(self._keys) - 1:
            return False
        self._index += 1
        return True
