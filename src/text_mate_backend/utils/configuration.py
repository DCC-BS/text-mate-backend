import os
from typing import override

from dcc_backend_common.config import AbstractAppConfig, get_env_or_throw, log_secret
from pydantic import Field




class Configuration(AbstractAppConfig, LlmConfig):
    client_url: str = Field(description="The URL for client application")
    llm_temperature: float = Field(description="The temperature for LLM API")
    llm_presence_penalty: float = Field(description="The presence penalty for LLM API")
    llm_top_p: float = Field(description="The top_p for LLM API")
    llm_top_k: int = Field(description="The top_k for LLM API")
    language_tool_api_url: str = Field(description="The URL for Language Tool API")

    docling_url: str = Field(description="The URL for Docling service")

    llm_health_check_url: str = Field(description="The URL for LLM health check API")
    language_tool_api_health_check_url: str = Field(description="The URL for Language Tool API health check API")

    azure_client_id: str = Field(description="The client ID for Azure AD application")
    azure_tenant_id: str = Field(description="The tenant ID for Azure AD application")
    azure_frontend_client_id: str = Field(description="The client ID for Azure AD frontend application")

    hmac_secret: str = Field(description="The secret key for HMAC authentication")
    azure_scope_description: str = Field(description="The scope description for Azure AD authentication")

    disable_auth: bool = Field(description="Flag to disable authentification")

    @classmethod
    @override
    def from_env(cls) -> "Configuration":
        language_tool_api_url = get_env_or_throw("LANGUAGE_TOOL_API_URL")
        language_tool_api_health_check_url = f"{language_tool_api_url.rstrip('/')}/languages"

        return cls(
            client_url=get_env_or_throw("CLIENT_URL"),
            openai_api_key=get_env_or_throw("OPENAI_API_KEY"),
            llm_url=get_env_or_throw("LLM_URL"),
            llm_model=get_env_or_throw("LLM_MODEL"),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            llm_presence_penalty=float(os.getenv("LLM_PRESENCE_PENALTY", "1.5")),
            llm_top_p=float(os.getenv("LLM_TOP_P", "0.8")),
            llm_top_k=int(os.getenv("LLM_TOP_K", "20")),
            language_tool_api_url=language_tool_api_url,
            language_tool_api_health_check_url=language_tool_api_health_check_url,
            docling_url=get_env_or_throw("DOCLING_URL"),
            llm_health_check_url=get_env_or_throw("LLM_HEALTH_CHECK_URL"),
            azure_client_id=get_env_or_throw("AZURE_CLIENT_ID"),
            azure_tenant_id=get_env_or_throw("AZURE_TENANT_ID"),
            azure_frontend_client_id=get_env_or_throw("AZURE_FRONTEND_CLIENT_ID"),
            azure_scope_description=get_env_or_throw("AZURE_SCOPE_DESCRIPTION"),
            hmac_secret=get_env_or_throw("HMAC_SECRET"),
            disable_auth=os.getenv("DISABLE_AUTH", "false").lower().strip() == "true",
        )

    @override
    def __str__(self) -> str:
        return f"""
        Configuration(
            client_url={self.client_url},
            openai_api_key={log_secret(self.openai_api_key)},
            llm_url={self.llm_url},
            llm_model={self.llm_model},
            llm_temperature={self.llm_temperature},
            llm_presence_penalty={self.llm_presence_penalty},
            llm_top_p={self.llm_top_p},
            llm_top_k={self.llm_top_k},
            language_tool_api_url={self.language_tool_api_url},
            language_tool_api_health_check_url={self.language_tool_api_health_check_url},
            docling_url={self.docling_url},
            llm_health_check_url={self.llm_health_check_url},
            azure_client_id={log_secret(self.azure_client_id)},
            azure_tenant_id={log_secret(self.azure_tenant_id)},
            azure_frontend_client_id={log_secret(self.azure_frontend_client_id)},
            azure_scope_description={self.azure_scope_description},
            hmac_secret={log_secret(self.hmac_secret)}
            disable_auth={self.disable_auth}
        )
        """
