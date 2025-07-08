from typing import final

import httpx
from cachetools import TTLCache
from fastapi import HTTPException, status

from text_mate_backend.utils.configuration import Configuration


@final
class AzureEntraService:
    key_cache: TTLCache[str, dict[str, list[dict[str, str]]]] = TTLCache(maxsize=1, ttl=3600)

    def __init__(self, config: Configuration):
        self.config = config
        self.azure_discovery_url = config.azure_discovery_url

    async def get_azure_public_keys(self) -> dict[str, list[dict[str, str]]]:
        cached_keys = self.key_cache.get("keys")
        if cached_keys:
            return cached_keys

        if not self.azure_discovery_url:
            raise ValueError("Azure discovery URL is not configured.")

        async with httpx.AsyncClient() as client:
            try:
                # 1. Get discovery document
                discovery_response = await client.get(self.azure_discovery_url)
                _ = discovery_response.raise_for_status()
                discovery_data: dict[str, str] = discovery_response.json()
                jwks_uri = discovery_data.get("jwks_uri")
                if not jwks_uri:
                    raise self._get_no_jwks_uri_exception()

                # 2. Get JWKS (public keys)
                jwks_response = await client.get(jwks_uri)
                _ = jwks_response.raise_for_status()
                jwks: dict[str, list[dict[str, str]]] = jwks_response.json()
                self.key_cache["keys"] = jwks
            except httpx.HTTPStatusError as e:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Failed to fetch Azure keys: {e.response.text}",
                ) from e
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching Azure keys: {e!s}"
                ) from e
            else:
                return jwks

    async def get_azure_public_key(self, key_id: str) -> dict[str, str]:
        keys = await self.get_azure_public_keys()
        for key in keys.get("keys", []):
            if key.get("kid") == key_id:
                return key
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Public key with ID {key_id} not found")

    def _get_no_jwks_uri_exception(self) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No JWKS URI found in discovery document"
        )
