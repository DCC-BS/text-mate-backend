import os
from typing import override

from dcc_backend_common.config import get_env_or_throw, log_secret
from dcc_backend_common.config.app_config import LlmConfig
from pydantic import Field


class Configuration(LlmConfig):
    client_url: str = Field(description="The URL for client application", default="http://localhost:3000")

    docling_url: str = Field(description="The URL for Docling service", default="http://localhost:5001/v1")
    docling_api_key: str = Field(
        description="The API key for Docling service, set it to none if none is required", default="none"
    )

    llm_health_check_url: str = Field(
        description="The URL for LLM health check API", default="http://localhost:8001/health"
    )

    azure_client_id: str = Field(description="The client ID for Azure AD application")
    azure_tenant_id: str = Field(description="The tenant ID for Azure AD application")
    azure_frontend_client_id: str = Field(description="The client ID for Azure AD frontend application")

    hmac_secret: str = Field(description="Used to pseudonymize user id. Create with openssl rand 32 | base64")
    azure_scope_description: str = Field(
        description="The scope description for Azure AD authentication", default="user_impersonation"
    )

    disable_auth: bool = Field(description="Flag to disable authentication", default=True)

    environment: str = Field(description="The application environment", default="development")

    @classmethod
    @override
    def from_env(cls) -> "Configuration":
        llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        disable_auth = os.getenv("AUTH_MODE", "none").lower().strip() == "none"

        if not llm_api_key:
            raise ValueError("LLM_API_KEY environment variable must be set")

        return cls(
            client_url=get_env_or_throw("CLIENT_URL"),
            llm_api_key=llm_api_key,
            llm_url=get_env_or_throw("LLM_URL"),
            llm_model=get_env_or_throw("LLM_MODEL"),
            docling_url=get_env_or_throw("DOCLING_URL"),
            docling_api_key=get_env_or_throw("DOCLING_API_KEY"),
            llm_health_check_url=get_env_or_throw("LLM_HEALTH_CHECK_URL"),
            azure_client_id="" if disable_auth else get_env_or_throw("AZURE_CLIENT_ID"),
            azure_tenant_id="" if disable_auth else get_env_or_throw("AZURE_TENANT_ID"),
            azure_frontend_client_id="" if disable_auth else get_env_or_throw("AZURE_FRONTEND_CLIENT_ID"),
            azure_scope_description="" if disable_auth else get_env_or_throw("AZURE_SCOPE_DESCRIPTION"),
            hmac_secret=get_env_or_throw("HMAC_SECRET"),
            disable_auth=disable_auth,
            environment="production" if os.getenv("APP_MODE", "prod") == "prod" else "development",
        )

    @override
    def __str__(self) -> str:
        return f"""
        Configuration(
            client_url={self.client_url},
            llm_api_key={log_secret(self.llm_api_key)},
            llm_url={self.llm_url},
            llm_model={self.llm_model},
            docling_url={self.docling_url},
            docling_api_key={log_secret(self.docling_api_key)},
            llm_health_check_url={self.llm_health_check_url},
            azure_client_id={log_secret(self.azure_client_id)},
            azure_tenant_id={log_secret(self.azure_tenant_id)},
            azure_frontend_client_id={log_secret(self.azure_frontend_client_id)},
            azure_scope_description={self.azure_scope_description},
            hmac_secret={log_secret(self.hmac_secret)}
            disable_auth={self.disable_auth}
            environment={self.environment}
        )
        """
