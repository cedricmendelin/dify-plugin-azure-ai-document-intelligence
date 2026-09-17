import unittest
from unittest.mock import Mock, patch

from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from provider.azure_ai_document_intelligence import AzureAiDocumentIntelligenceProvider


class ProviderValidationTests(unittest.TestCase):
    @patch("provider.azure_ai_document_intelligence.DocumentIntelligenceAdministrationClient")
    def test_uses_normalized_endpoint_and_configured_api_version(self, client_type: Mock) -> None:
        client = client_type.return_value.__enter__.return_value

        AzureAiDocumentIntelligenceProvider._validate_credentials(
            object(),
            {
                "api_endpoint": "https://example.cognitiveservices.azure.com/",
                "api_key": "test-key",
                "api_version": "2024-11-30",
            },
        )

        client_type.assert_called_once()
        self.assertEqual(
            client_type.call_args.kwargs["endpoint"],
            "https://example.cognitiveservices.azure.com",
        )
        self.assertEqual(client_type.call_args.kwargs["api_version"], "2024-11-30")
        client.get_model.assert_called_once_with("prebuilt-layout")

    @patch("provider.azure_ai_document_intelligence.DocumentIntelligenceAdministrationClient")
    def test_rejects_unsupported_api_version_before_request(self, client_type: Mock) -> None:
        with self.assertRaisesRegex(
            ToolProviderCredentialValidationError,
            "Unsupported API version",
        ):
            AzureAiDocumentIntelligenceProvider._validate_credentials(
                object(),
                {
                    "api_endpoint": "https://example.cognitiveservices.azure.com/",
                    "api_key": "test-key",
                    "api_version": "2026-06-01-preview",
                },
            )

        client_type.assert_not_called()

    @patch("provider.azure_ai_document_intelligence.DocumentIntelligenceAdministrationClient")
    def test_wraps_sdk_validation_errors(self, client_type: Mock) -> None:
        client_type.return_value.__enter__.return_value.get_model.side_effect = RuntimeError("access denied")

        with self.assertRaisesRegex(
            ToolProviderCredentialValidationError,
            "access denied",
        ):
            AzureAiDocumentIntelligenceProvider._validate_credentials(
                object(),
                {
                    "api_endpoint": "https://example.cognitiveservices.azure.com/",
                    "api_key": "test-key",
                },
            )


if __name__ == "__main__":
    unittest.main()
