from typing import Any, final

from fastapi import HTTPException, status
from jose import jwt
from jose.exceptions import JWTError
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from text_mate_backend.services.azure_entra_service import AzureEntraService
from text_mate_backend.utils.configuration import Configuration


@final
class JWTAuthMiddleware:
    def __init__(
        self, app: ASGIApp, config: Configuration, azure_entra_service: AzureEntraService, unprotected_routes: list[str]
    ):
        self.app = app
        self.unprotected_routes = unprotected_routes
        self.config = config
        self.azure_entra_service = azure_entra_service

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            path: str = scope["path"]

            if any(path.startswith(route) for route in self.unprotected_routes):
                await self.app(scope, receive, send)
                return

            request: Request = Request(scope, receive=receive)
            auth_header: str | None = request.headers.get("Authorization")

            if not auth_header or not auth_header.startswith("Bearer "):
                response = JSONResponse(
                    {"detail": "Not authenticated"},
                    status_code=401,
                )

                await response(scope, receive, send)
                return

            # access_token = request.headers.get("X-Access-Token")

            # if not access_token:
            #     response = JSONResponse(
            #         {"detail": "Access token not provided"},
            #         status_code=401,
            #     )

            #     await response(scope, receive, send)
            #     return

            token: str = auth_header.split(" ")[1]
            unverified_header: dict[str, str] | None = None

            try:
                unverified_header = jwt.get_unverified_header(token)
                if not unverified_header or "kid" not in unverified_header:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid token header",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            except JWTError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not validate credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from JWTError

            rsa_key = await self.azure_entra_service.get_azure_public_key(unverified_header["kid"])

            print("token", token)

            try:
                payload: dict[str, Any] = jwt.decode(
                    token,
                    rsa_key,
                    algorithms=["RS256"],
                    audience=self.config.azure_client_id,
                    issuer=f"https://login.microsoftonline.com/{self.config.azure_tenant_id}/v2.0",
                    # access_token=access_token,
                )

                scope["user"] = payload

            except JWTError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not validate credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from e

        await self.app(scope, receive, send)
