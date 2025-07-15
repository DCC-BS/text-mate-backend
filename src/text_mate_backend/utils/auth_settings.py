from pydantic import BaseModel

from text_mate_backend.utils.configuration import Configuration


class AuthSettings(BaseModel):
    openapi_client_id: str = ""
    app_client_id: str = ""
    tenant_id: str = ""
    scope_description: str = "all_access"

    def __init__(self, config: Configuration):
        super().__init__(
            openapi_client_id=config.azure_open_api_client_id,
            app_client_id=config.azure_app_client_id,
            tenant_id=config.azure_tenant_id,
        )

    @property
    def scope_name(self) -> str:
        return f"api://{self.app_client_id}/{self.scope_description}"

    @property
    def scopes(self) -> dict:
        return {
            self.scope_name: self.scope_description,
        }

    @property
    def openapi_authorization_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize"

    @property
    def openapi_token_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
