import os
import unittest
from unittest.mock import patch

from gemini_keys import get_gemini_api_key, is_rate_limit_error


class ApiErrorStub(Exception):
    def __init__(self, message: str, code=None):
        super().__init__(message)
        self.code = code
        self.message = message


class GeminiKeysTests(unittest.TestCase):
    def test_trims_explicit_key(self):
        self.assertEqual(get_gemini_api_key(" first-key "), "first-key")

    def test_falls_back_to_google_api_key(self):
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": "backup-key"},
            clear=False,
        ):
            self.assertEqual(get_gemini_api_key(), "backup-key")

    def test_recognizes_sdk_rate_limit_shapes(self):
        self.assertTrue(is_rate_limit_error(ApiErrorStub("limited", code=429)))
        self.assertTrue(
            is_rate_limit_error(ApiErrorStub("limited", code="rate_limit_exceeded"))
        )
        self.assertTrue(is_rate_limit_error(ApiErrorStub("429 RESOURCE_EXHAUSTED")))
        self.assertFalse(is_rate_limit_error(ApiErrorStub("503 UNAVAILABLE", code=503)))

if __name__ == "__main__":
    unittest.main()
