![Icon](./_assets/00819-icon-service-Form-Recognizers.svg)

# Azure AI Document Intelligence

[![GitHub Repo](https://img.shields.io/badge/GitHub_Repo-fujita--h/dify--plugin--azure--ai--document--intelligence-blue?logo=github)](https://github.com/fujita-h/dify-plugin-azure-ai-document-intelligence)  
[![GitHub Release](https://img.shields.io/github/v/release/fujita-h/dify-plugin-azure-ai-document-intelligence)](https://github.com/fujita-h/dify-plugin-azure-ai-document-intelligence/releases)
[![GitHub License](https://img.shields.io/github/license/fujita-h/dify-plugin-azure-ai-document-intelligence)](https://github.com/fujita-h/dify-plugin-azure-ai-document-intelligence/blob/main/LICENSE)

This plugin provides tools to extract text from a document using the Azure AI Document Intelligence service.

> [!IMPORTANT]  
> This plugin requires an Azure subscription. If you don't have an Azure subscription, create a free account before you begin. Learn more about the free trial [here](https://azure.microsoft.com/free/).

## Tools provided by this plugin

### Extract Document

This tool extracts text from a document using the Azure AI Document Intelligence service. The tool takes a document as input and returns the **Extracted Text** or **Markdown**.
Supported document formats include PDF, JPEG, JPG, PNG, BMP, TIFF, HEIF, DOCX, XLSX, PPTX, and HTML.  

Learn more about the Document Layout Analysis API v4.0 [here](https://learn.microsoft.com/azure/ai-services/document-intelligence/prebuilt/layout?view=doc-intel-4.0.0).

The tool also supports:

- Optional comma-separated 1-based page ranges (e.g. `1-10, 11-20, 21-50`). Each range is analyzed separately and concurrently, and returned in input order as one element `{first_page, last_page, content}` of the `segments` output; the `text` output contains all segments joined by a blank line. Ranges may be entered in any order, may overlap, and are limited to 20. This replaces the former first/last page settings (breaking change in 0.1.0).
- Optional removal of Markdown lines containing Azure `PageHeader` comments. This is disabled by default to preserve existing output.
- A provider-level API version setting. The installed Azure AI Document Intelligence SDK supports `2024-11-30`; unsupported versions are rejected before a request is sent.

## Configuration and Usage

See [Plugin README](./README.difypkg.md) for configuration and usage details.

## Notes

This plugin uses the Document Layout Analysis API v4.0 of the [Azure AI Document Intelligence](https://azure.microsoft.com/products/ai-services/ai-document-intelligence) service. Please refer to the official documentation for more information.

This plugin does not use Azure AI Content Understanding. Content Understanding endpoints, API versions, and analyzers are not interchangeable with Azure AI Document Intelligence.

## Contributing

This plugin is open-source and contributions are welcome.
