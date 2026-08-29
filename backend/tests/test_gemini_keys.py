import os
import unittest
from unittest.mock import patch

from gemini_keys import GeminiKeyRing, get_gemini_api_keys, is_rate_limit_error


class ApiErrorStub(Exception):
    def __init__(self, message: str, code=None):
        super().__init__(message)
        self.code = code
        self.message = message


class GeminiKeysTests(unittest.TestCase):
    def test_parses_trims_and_deduplicates_comma_separated_keys(self):
        self.assertEqual(
            get_gemini_api_keys(" first-key, second-key, first-key, ,third-key "),
            ["first-key", "second-key", "third-key"],
        )

    def test_falls_back_to_google_api_key(self):
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": "backup-one,backup-two"},
            clear=False,
        ):
            self.assertEqual(
                get_gemini_api_keys(),
                ["backup-one", "backup-two"],
            )

    def test_recognizes_sdk_rate_limit_shapes(self):
        self.assertTrue(is_rate_limit_error(ApiErrorStub("limited", code=429)))
        self.assertTrue(
            is_rate_limit_error(ApiErrorStub("limited", code="rate_limit_exceeded"))
        )
        self.assertTrue(is_rate_limit_error(ApiErrorStub("429 RESOURCE_EXHAUSTED")))
        self.assertFalse(is_rate_limit_error(ApiErrorStub("503 UNAVAILABLE", code=503)))

    def test_key_ring_advances_only_for_rate_limits(self):
        ring = GeminiKeyRing(["first-key", "second-key"])

        self.assertFalse(ring.advance_for(ApiErrorStub("unavailable", code=503)))
        self.assertEqual(ring.current, "first-key")
        self.assertTrue(ring.advance_for(ApiErrorStub("limited", code=429)))
        self.assertEqual(ring.current, "second-key")
        self.assertFalse(ring.advance_for(ApiErrorStub("limited", code=429)))


if __name__ == "__main__":
    unittest.main()
