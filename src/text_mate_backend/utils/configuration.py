import os
from typing import override


class Configuration:
    def __init__(self) -> None:
        self.openai_api_base_url: str = os.getenv("OPENAI_API_BASE_URL", "http://localhost:8000/v1")
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "none")
        self.llm_model: str = os.getenv("LLM_MODEL", "ollama_chat/llama3.2")
        self.language_tool_api_url: str = os.getenv("LANGUAGE_TOOL_API_URL", "http://localhost:8010/")
        self.client_url: str = os.getenv("CLIENT_URL", "http://localhost:3000")

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

    @override
    def __str__(self) -> str:
        return f"""
        Configuration(
            client_url={self.client_url},
            openai_api_base_url={self.openai_api_base_url},
            openai_api_key={self.openai_api_key},
            llm_model={self.llm_model},
            language_tool_api_url={self.language_tool_api_url},
            azure_client_id={self.azure_client_id},
            azure_tenant_id={self.azure_tenant_id},
            azure_discovery_url={self.azure_discovery_url})
        """
