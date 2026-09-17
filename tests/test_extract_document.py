import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tools.extract_document import (
    ExtractDocumentTool,
    _build_page_range,
    _remove_page_headers,
)


class PageRangeTests(unittest.TestCase):
    def test_omits_range_when_bounds_are_missing(self) -> None:
        self.assertIsNone(_build_page_range(None, None))

    def test_builds_supported_range_combinations(self) -> None:
        self.assertEqual(_build_page_range(2, 5), "2-5")
        self.assertEqual(_build_page_range(2, None), "2")
        self.assertEqual(_build_page_range(None, 5), "1-5")
        self.assertEqual(_build_page_range(3, 3), "3")

    def test_accepts_integer_values_from_form_inputs(self) -> None:
        self.assertEqual(_build_page_range(2.0, "4"), "2-4")

    def test_rejects_invalid_page_values(self) -> None:
        for first, last in [(0, None), (1.5, None), ("one", None), (True, None), (3, 2)]:
            with self.subTest(first=first, last=last), self.assertRaises(ValueError):
                _build_page_range(first, last)


class PageHeaderTests(unittest.TestCase):
    def test_removes_only_lines_containing_page_header_comments(self) -> None:
        content = "# Title\n<!-- PageHeader: Confidential -->\nBody\n<!-- PageFooter: 1 -->"

        self.assertEqual(_remove_page_headers(content), "# Title\nBody\n<!-- PageFooter: 1 -->")


class ExtractDocumentToolTests(unittest.TestCase):
    @patch("tools.extract_document.DocumentIntelligenceClient")
    def test_propagates_api_version_range_and_filters_markdown_headers(self, client_type: Mock) -> None:
        poller = Mock()
        poller.result.return_value = SimpleNamespace(content="# Title\n<!-- PageHeader: Confidential -->\nBody")
        client_type.return_value.begin_analyze_document.return_value = poller
        tool = SimpleNamespace(
            runtime=SimpleNamespace(
                credentials={
                    "api_endpoint": "https://example.cognitiveservices.azure.com/",
                    "api_key": "test-key",
                    "api_version": "2024-11-30",
                }
            ),
            create_text_message=lambda content: content,
        )
        parameters = {
            "input_file": SimpleNamespace(blob=b"document"),
            "output_format": "markdown",
            "first_page": 2,
            "last_page": 4,
            "remove_page_headers": True,
        }

        messages = list(ExtractDocumentTool._invoke(tool, parameters))

        self.assertEqual(messages, ["# Title\nBody"])
        client_type.assert_called_once()
        self.assertEqual(
            client_type.call_args.args[0],
            "https://example.cognitiveservices.azure.com",
        )
        self.assertEqual(client_type.call_args.kwargs["api_version"], "2024-11-30")
        client_type.return_value.begin_analyze_document.assert_called_once()
        analyze_kwargs = client_type.return_value.begin_analyze_document.call_args.kwargs
        self.assertEqual(analyze_kwargs["pages"], "2-4")
        self.assertEqual(analyze_kwargs["output_content_format"], "markdown")

    @patch("tools.extract_document.DocumentIntelligenceClient")
    def test_preserves_headers_by_default(self, client_type: Mock) -> None:
        content = "<!-- PageHeader: Confidential -->\nBody"
        poller = Mock()
        poller.result.return_value = SimpleNamespace(content=content)
        client_type.return_value.begin_analyze_document.return_value = poller
        tool = SimpleNamespace(
            runtime=SimpleNamespace(
                credentials={
                    "api_endpoint": "https://example.cognitiveservices.azure.com/",
                    "api_key": "test-key",
                }
            ),
            create_text_message=lambda value: value,
        )
        parameters = {
            "input_file": SimpleNamespace(blob=b"document"),
            "output_format": "markdown",
        }

        messages = list(ExtractDocumentTool._invoke(tool, parameters))

        self.assertEqual(messages, [content])
        self.assertIsNone(client_type.return_value.begin_analyze_document.call_args.kwargs["pages"])

    @patch("tools.extract_document.DocumentIntelligenceClient")
    def test_rejects_unsupported_api_version_before_creating_client(self, client_type: Mock) -> None:
        tool = SimpleNamespace(
            runtime=SimpleNamespace(
                credentials={
                    "api_endpoint": "https://example.cognitiveservices.azure.com/",
                    "api_key": "test-key",
                    "api_version": "2026-06-01-preview",
                }
            )
        )

        with self.assertRaisesRegex(ValueError, "Unsupported API version"):
            list(
                ExtractDocumentTool._invoke(
                    tool,
                    {
                        "input_file": SimpleNamespace(blob=b"document"),
                        "output_format": "markdown",
                    },
                )
            )

        client_type.assert_not_called()


if __name__ == "__main__":
    unittest.main()
