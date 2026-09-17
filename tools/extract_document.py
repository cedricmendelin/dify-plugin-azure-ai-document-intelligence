import io
from collections.abc import Generator
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from azure_config import validate_api_version


def _parse_page_number(value: object, parameter_name: str) -> int | None:
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        raise ValueError(f"{parameter_name} must be a positive integer")

    if isinstance(value, int):
        page_number = value
    elif isinstance(value, float) and value.is_integer():
        page_number = int(value)
    elif isinstance(value, str) and value.strip().isdigit():
        page_number = int(value.strip())
    else:
        raise ValueError(f"{parameter_name} must be a positive integer")

    if page_number < 1:
        raise ValueError(f"{parameter_name} must be a positive integer")
    return page_number


def _build_page_range(first_page: object, last_page: object) -> str | None:
    first = _parse_page_number(first_page, "First page")
    last = _parse_page_number(last_page, "Last page")

    if first is None and last is None:
        return None
    if first is None:
        return f"1-{last}"
    if last is None:
        return str(first)
    if last < first:
        raise ValueError("Last page must be greater than or equal to first page")
    return str(first) if first == last else f"{first}-{last}"


def _remove_page_headers(content: str) -> str:
    return "\n".join(line for line in content.splitlines() if "<!-- PageHeader:" not in line).strip()


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

        # Create credential
        credential = AzureKeyCredential(api_key)

        # Get file
        file = tool_parameters.get("input_file")
        if not file:
            raise ValueError("File is required")
        file_binary = io.BytesIO(file.blob)

        # Get output format
        output_format = tool_parameters.get("output_format")
        pages = _build_page_range(
            tool_parameters.get("first_page"),
            tool_parameters.get("last_page"),
        )
        remove_page_headers = tool_parameters.get("remove_page_headers", False) is True

        # Create client and analyze document
        document_analysis_client = DocumentIntelligenceClient(
            endpoint,
            credential,
            api_version=api_version,
        )
        poller = document_analysis_client.begin_analyze_document(
            model_id="prebuilt-layout",
            body=file_binary,
            content_type="application/octet-stream",
            output_content_format="markdown" if output_format == "markdown" else None,
            pages=pages,
        )
        result = poller.result()
        content = result.content

        if output_format == "markdown" and remove_page_headers:
            content = _remove_page_headers(content)

        yield self.create_text_message(content)
