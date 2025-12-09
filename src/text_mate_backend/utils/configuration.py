import os
from typing import override


def log_secret(secret: str | None) -> str:
    return "****" if secret is not None and len(secret) > 0 else "None"


class Configuration:
    def __init__(self) -> None:
        """
        Initialize Configuration by reading required and optional environment variables.
        
        Reads environment variables to populate configuration attributes (with defaults when shown):
        - OPENAI_API_BASE_URL (default "http://localhost:8000/v1")
        - OPENAI_API_KEY (default "none")
        - LLM_MODEL (default "ollama_chat/llama3.2")
        - LANGUAGE_TOOL_API_URL (default "http://localhost:8010/")
        - CLIENT_URL (default "http://localhost:3000")
        - DOCLING_URL (default "http://localhost:5001")
        - LLM_HEALTH_CHECK_URL (required; if unset, raises RuntimeError("LLM_HEALTH_CHECK_URL is not set"))
        - AZURE_CLIENT_ID (optional)
        - AZURE_TENANT_ID (optional; when present, derives azure_discovery_url as "https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration")
        - AZURE_FRONTEND_CLIENT_ID (optional)
        - SCOPE_DESCRIPTION (default "")
        - HMAC_SECRET (default "none"; if equal to "none", raises RuntimeError("HMAC secret is not set"))
        
        Also derives language_tool_api_health_check_url by appending "/languages" to LANGUAGE_TOOL_API_URL with trailing slash normalized.
        """
        self.openai_api_base_url: str = os.getenv("OPENAI_API_BASE_URL", "http://localhost:8000/v1")
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "none")
        self.llm_model: str = os.getenv("LLM_MODEL", "ollama_chat/llama3.2")
        self.language_tool_api_url: str = os.getenv("LANGUAGE_TOOL_API_URL", "http://localhost:8010/")
        self.client_url: str = os.getenv("CLIENT_URL", "http://localhost:3000")
        self.docling_url: str = os.getenv("DOCLING_URL", "http://localhost:5001")

        llm_health_check_url: str | None = os.getenv("LLM_HEALTH_CHECK_URL")
        if llm_health_check_url is None:
            raise RuntimeError("LLM_HEALTH_CHECK_URL is not set")
        self.llm_health_check_url: str = llm_health_check_url

        self.language_tool_api_health_check_url = f"{self.language_tool_api_url.rstrip("/")}/languages"

        self.azure_client_id: str | None = os.getenv("AZURE_CLIENT_ID")
        self.azure_tenant_id: str | None = os.getenv("AZURE_TENANT_ID")
        self.azure_frontend_client_id: str | None = os.getenv("AZURE_FRONTEND_CLIENT_ID")
        self.azure_discovery_url: str | None = (
            f"https://login.microsoftonline.com/{self.azure_tenant_id}/v2.0/.well-known/openid-configuration"
            if self.azure_tenant_id
            else None
        )
        self.azure_scope_description: str = os.getenv("SCOPE_DESCRIPTION", "")
        self.hmac_secret: str = os.getenv("HMAC_SECRET", "none")
        if self.hmac_secret == "none":
            raise RuntimeError("HMAC secret is not set")

    @override
    def __str__(self) -> str:
        return f"""
        Configuration(
            client_url={self.client_url},
            openai_api_base_url={self.openai_api_base_url},
            openai_api_key={log_secret(self.openai_api_key)},
            llm_model={self.llm_model},
            language_tool_api_url={self.language_tool_api_url},
            docling_url={self.docling_url},
            azure_client_id={log_secret(self.azure_client_id)},
            azure_tenant_id={log_secret(self.azure_tenant_id)},
            azure_discovery_url={log_secret(self.azure_discovery_url)},
            azure_frontend_client_id={log_secret(self.azure_frontend_client_id)},
            azure_scope_description={self.azure_scope_description},
            hmac_secret={log_secret(self.hmac_secret)}
        )
        """