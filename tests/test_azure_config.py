import unittest

from azure_config import DEFAULT_API_VERSION, validate_api_version


class ValidateApiVersionTests(unittest.TestCase):
    def test_defaults_missing_or_blank_versions(self) -> None:
        self.assertEqual(validate_api_version(None), DEFAULT_API_VERSION)
        self.assertEqual(validate_api_version("  "), DEFAULT_API_VERSION)

    def test_accepts_supported_version(self) -> None:
        self.assertEqual(validate_api_version(" 2024-11-30 "), "2024-11-30")

    def test_rejects_unsupported_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "Supported API versions.*2024-11-30"):
            validate_api_version("2026-06-01-preview")


if __name__ == "__main__":
    unittest.main()
