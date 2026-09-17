from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceAdministrationClient
from azure.core.credentials import AzureKeyCredential
from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from azure_config import validate_api_version


class AzureAiDocumentIntelligenceProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            api_endpoint = str(credentials.get("api_endpoint", "")).strip().rstrip("/")
            api_key = str(credentials.get("api_key", "")).strip()
            api_version = validate_api_version(credentials.get("api_version"))

            # Ensure API key and endpoint are provided
            if not api_endpoint:
                raise Exception("API endpoint is missing")
            if not api_key:
                raise Exception("API key is missing")

            with DocumentIntelligenceAdministrationClient(
                endpoint=api_endpoint,
                credential=AzureKeyCredential(api_key),
                api_version=api_version,
            ) as client:
                client.get_model("prebuilt-layout")

        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e)) from e
