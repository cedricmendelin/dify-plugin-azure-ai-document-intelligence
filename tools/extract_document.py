import io
import re
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from typing import Any, NamedTuple

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from azure_config import validate_api_version

MAX_PAGE_RANGES = 20
_RANGE_PATTERN = re.compile(r"^(\d+)(?:\s*-\s*(\d+))?$")


class PageRange(NamedTuple):
    first_page: int
    last_page: int

    def to_azure(self) -> str:
        if self.first_page == self.last_page:
            return str(self.first_page)
        return f"{self.first_page}-{self.last_page}"


def _parse_page_ranges(value: object) -> list[PageRange]:
    if value is None:
        return []
    if not isinstance(value, str):
        raise ValueError("Page ranges must be a string such as '1-10, 11-20'")

    tokens = [token.strip() for token in value.split(",")]
    if all(token == "" for token in tokens):
        return []

    ranges: list[PageRange] = []
    for token in tokens:
        match = _RANGE_PATTERN.match(token)
        if not match:
            raise ValueError(f"Invalid page range '{token}': use a page number like '5' or a range like '1-10'")
        first = int(match.group(1))
        last = int(match.group(2)) if match.group(2) is not None else first
        if first < 1:
            raise ValueError(f"Invalid page range '{token}': page numbers must be positive integers")
        if last < first:
            raise ValueError(f"Invalid page range '{token}': last page must be greater than or equal to first page")
        ranges.append(PageRange(first, last))

    if len(ranges) > MAX_PAGE_RANGES:
        raise ValueError(f"Too many page ranges: at most {MAX_PAGE_RANGES} are allowed, got {len(ranges)}")
    return ranges


def _remove_page_headers(content: str) -> str:
    return "\n".join(line for line in content.splitlines() if "<!-- PageHeader:" not in line).strip()


def _analyze(
    client: DocumentIntelligenceClient,
    file_bytes: bytes,
    output_format: object,
    remove_page_headers: bool,
    pages: str | None,
) -> str:
    poller = client.begin_analyze_document(
        model_id="prebuilt-layout",
        body=io.BytesIO(file_bytes),
        content_type="application/octet-stream",
        output_content_format="markdown" if output_format == "markdown" else None,
        pages=pages,
    )
    content = poller.result().content or ""

    if output_format == "markdown" and remove_page_headers:
        content = _remove_page_headers(content)
    return content


def _analyze_page_range(
    endpoint: str,
    api_key: str,
    api_version: str,
    file_bytes: bytes,
    output_format: object,
    remove_page_headers: bool,
    page_range: PageRange,
) -> str:
    client = DocumentIntelligenceClient(
        endpoint,
        AzureKeyCredential(api_key),
        api_version=api_version,
    )
    try:
        return _analyze(
            client,
            file_bytes,
            output_format,
            remove_page_headers,
            page_range.to_azure(),
        )
    finally:
        client.close()


class ExtractDocumentTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        # Ensure runtime and credentials
        if not self.runtime or not self.runtime.credentials:
            raise Exception("Tool runtime or credentials are missing")

        # Get endpoint and api key
        endpoint = str(self.runtime.credentials.get("api_endpoint", "")).strip().rstrip("/")
        api_key = str(self.runtime.credentials.get("api_key", "")).strip()
        api_version = validate_api_version(self.runtime.credentials.get("api_version"))

        # Check if endpoint and api key are provided
        if not endpoint:
            raise ValueError("API endpoint is missing")
        if not api_key:
            raise ValueError("API key is missing")

        # Get file
        file = tool_parameters.get("input_file")
        if not file:
            raise ValueError("File is required")

        output_format = tool_parameters.get("output_format")
        page_ranges = _parse_page_ranges(tool_parameters.get("page_ranges"))
        remove_page_headers = tool_parameters.get("remove_page_headers", False) is True

        if not page_ranges:
            client = DocumentIntelligenceClient(
                endpoint,
                AzureKeyCredential(api_key),
                api_version=api_version,
            )
            yield self.create_text_message(_analyze(client, file.blob, output_format, remove_page_headers, None))
            return

        segments: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=len(page_ranges)) as executor:
            futures = [
                (
                    page_range,
                    executor.submit(
                        _analyze_page_range,
                        endpoint,
                        api_key,
                        api_version,
                        file.blob,
                        output_format,
                        remove_page_headers,
                        page_range,
                    ),
                )
                for page_range in page_ranges
            ]
            for page_range, future in futures:
                pages = page_range.to_azure()
                try:
                    content = future.result()
                except Exception as error:
                    raise ValueError(f"Failed to analyze pages {pages}: {error}") from error
                segments.append(
                    {
                        "first_page": page_range.first_page,
                        "last_page": page_range.last_page,
                        "content": content,
                    }
                )

        yield self.create_text_message("\n\n".join(segment["content"] for segment in segments))
        yield self.create_json_message({"segments": segments})
        yield self.create_variable_message("segments", segments)
