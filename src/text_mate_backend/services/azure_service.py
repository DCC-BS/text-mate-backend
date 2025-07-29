from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer

from text_mate_backend.utils.auth_settings import AuthSettings


class AzureService:
    def __init__(self, auth_settings: AuthSettings):
        self.azure_scheme = SingleTenantAzureAuthorizationCodeBearer(
            app_client_id=auth_settings.app_client_id,
            tenant_id=auth_settings.tenant_id,
            scopes=auth_settings.scopes,
        )

    async def load_config(self) -> None:
        """
        Load the Azure configuration from the provided configuration object.
        """
        await self.azure_scheme.openid_config.load_config()
