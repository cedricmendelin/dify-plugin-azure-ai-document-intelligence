DEFAULT_API_VERSION = "2024-11-30"
SUPPORTED_API_VERSIONS = frozenset({DEFAULT_API_VERSION})


def validate_api_version(value: object) -> str:
    api_version = str(value or "").strip() or DEFAULT_API_VERSION
    if api_version not in SUPPORTED_API_VERSIONS:
        supported_versions = ", ".join(sorted(SUPPORTED_API_VERSIONS))
        raise ValueError(
            f"Unsupported API version '{api_version}'. "
            f"Supported API versions for the installed Azure SDK: {supported_versions}."
        )
    return api_version
