import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tools.extract_document import (
    MAX_PAGE_RANGES,
    ExtractDocumentTool,
    PageRange,
    _parse_page_ranges,
    _remove_page_headers,
)


def _make_tool(credentials: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        runtime=SimpleNamespace(
            credentials=credentials
            or {
                "api_endpoint": "https://example.cognitiveservices.azure.com/",
                "api_key": "test-key",
                "api_version": "2024-11-30",
            }
        ),
        create_text_message=lambda value: ("text", value),
        create_json_message=lambda value: ("json", value),
        create_variable_message=lambda name, value: ("variable", name, value),
    )


def _mock_results(client_type: Mock, contents: list[str]) -> None:
    pollers = []
    for content in contents:
        poller = Mock()
        poller.result.return_value = SimpleNamespace(content=content)
        pollers.append(poller)
    client_type.return_value.begin_analyze_document.side_effect = pollers


class PageRangeParsingTests(unittest.TestCase):
    def test_empty_values_mean_whole_document(self) -> None:
        for value in [None, "", "   ", " , "]:
            with self.subTest(value=value):
                self.assertEqual(_parse_page_ranges(value), [])

    def test_parses_single_pages_and_ranges(self) -> None:
        self.assertEqual(
            _parse_page_ranges("1-10, 11-20 ,21 - 50"),
            [PageRange(1, 10), PageRange(11, 20), PageRange(21, 50)],
        )
        self.assertEqual(_parse_page_ranges("5,7-9"), [PageRange(5, 5), PageRange(7, 9)])

    def test_allows_overlapping_ranges(self) -> None:
        self.assertEqual(_parse_page_ranges("1-10, 5-15"), [PageRange(1, 10), PageRange(5, 15)])

    def test_azure_format(self) -> None:
        self.assertEqual(PageRange(3, 3).to_azure(), "3")
        self.assertEqual(PageRange(1, 10).to_azure(), "1-10")

    def test_rejects_invalid_ranges(self) -> None:
        for value in ["0", "0-3", "5-3", "11-", "-5", "one", "1-2-3", "1.5", "11-20, 1-10", "1,,2", 5]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                _parse_page_ranges(value)

    def test_limits_number_of_ranges(self) -> None:
        allowed = ",".join(str(page) for page in range(1, MAX_PAGE_RANGES + 1))
        self.assertEqual(len(_parse_page_ranges(allowed)), MAX_PAGE_RANGES)
        with self.assertRaisesRegex(ValueError, "Too many page ranges"):
            _parse_page_ranges(allowed + f",{MAX_PAGE_RANGES + 1}")

    def test_error_names_offending_token(self) -> None:
        with self.assertRaisesRegex(ValueError, "'11-'"):
            _parse_page_ranges("1-10, 11-")


class PageHeaderTests(unittest.TestCase):
    def test_removes_only_lines_containing_page_header_comments(self) -> None:
        content = "# Title\n<!-- PageHeader: Confidential -->\nBody\n<!-- PageFooter: 1 -->"

        self.assertEqual(_remove_page_headers(content), "# Title\nBody\n<!-- PageFooter: 1 -->")


class ExtractDocumentToolTests(unittest.TestCase):
    @patch("tools.extract_document.DocumentIntelligenceClient")
    def test_whole_document_returns_text_only(self, client_type: Mock) -> None:
        content = "<!-- PageHeader: Confidential -->\nBody"
        _mock_results(client_type, [content])
        tool = _make_tool(
            {
                "api_endpoint": "https://example.cognitiveservices.azure.com/",
                "api_key": "test-key",
            }
        )
        parameters = {
            "input_file": SimpleNamespace(blob=b"document"),
            "output_format": "markdown",
        }

        messages = list(ExtractDocumentTool._invoke(tool, parameters))

        self.assertEqual(messages, [("text", content)])
        client_type.return_value.begin_analyze_document.assert_called_once()
        self.assertIsNone(client_type.return_value.begin_analyze_document.call_args.kwargs["pages"])

    @patch("tools.extract_document.DocumentIntelligenceClient")
    def test_analyzes_each_range_separately(self, client_type: Mock) -> None:
        _mock_results(
            client_type,
            [
                "# A\n<!-- PageHeader: X -->\nOne",
                "# B\nTwo",
                "<!-- PageHeader: Y -->\nThree",
            ],
        )
        tool = _make_tool()
        parameters = {
            "input_file": SimpleNamespace(blob=b"document"),
            "output_format": "markdown",
            "page_ranges": "1-10, 5-20, 21",
            "remove_page_headers": True,
        }

        messages = list(ExtractDocumentTool._invoke(tool, parameters))

        segments = [
            {"first_page": 1, "last_page": 10, "content": "# A\nOne"},
            {"first_page": 5, "last_page": 20, "content": "# B\nTwo"},
            {"first_page": 21, "last_page": 21, "content": "Three"},
        ]
        self.assertEqual(
            messages,
            [
                ("text", "# A\nOne\n\n# B\nTwo\n\nThree"),
                ("json", {"segments": segments}),
                ("variable", "segments", segments),
            ],
        )
        client_type.assert_called_once()
        self.assertEqual(client_type.call_args.args[0], "https://example.cognitiveservices.azure.com")
        self.assertEqual(client_type.call_args.kwargs["api_version"], "2024-11-30")
        calls = client_type.return_value.begin_analyze_document.call_args_list
        self.assertEqual([call.kwargs["pages"] for call in calls], ["1-10", "5-20", "21"])
        self.assertTrue(all(call.kwargs["output_content_format"] == "markdown" for call in calls))
        self.assertTrue(all(call.kwargs["body"].read() == b"document" for call in calls))

    @patch("tools.extract_document.DocumentIntelligenceClient")
    def test_failed_range_fails_whole_call_with_range_in_message(self, client_type: Mock) -> None:
        ok = Mock()
        ok.result.return_value = SimpleNamespace(content="One")
        client_type.return_value.begin_analyze_document.side_effect = [ok, RuntimeError("InvalidContentRange")]
        parameters = {
            "input_file": SimpleNamespace(blob=b"document"),
            "output_format": "text",
            "page_ranges": "1-10, 21-50",
        }

        with self.assertRaisesRegex(ValueError, "Failed to analyze pages 21-50: InvalidContentRange"):
            list(ExtractDocumentTool._invoke(_make_tool(), parameters))

    @patch("tools.extract_document.DocumentIntelligenceClient")
    def test_invalid_ranges_fail_before_calling_azure(self, client_type: Mock) -> None:
        parameters = {
            "input_file": SimpleNamespace(blob=b"document"),
            "output_format": "text",
            "page_ranges": "11-20, 1-10",
        }

        with self.assertRaisesRegex(ValueError, "ascending order"):
            list(ExtractDocumentTool._invoke(_make_tool(), parameters))

        client_type.assert_not_called()

    @patch("tools.extract_document.DocumentIntelligenceClient")
    def test_rejects_unsupported_api_version_before_creating_client(self, client_type: Mock) -> None:
        tool = _make_tool(
            {
                "api_endpoint": "https://example.cognitiveservices.azure.com/",
                "api_key": "test-key",
                "api_version": "2026-06-01-preview",
            }
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
