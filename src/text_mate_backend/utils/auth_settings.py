from authentication import AzureEntraSettings

from text_mate_backend.utils.configuration import Configuration


class AuthSettings(AzureEntraSettings):
    def __init__(self, config: Configuration):
        if not config.azure_client_id or not config.azure_tenant_id:
            raise ValueError("Azure client ID and tenant ID must be set in the configuration.")

        super().__init__(azure_client_id=config.azure_client_id, azure_tenant_id=config.azure_tenant_id)
