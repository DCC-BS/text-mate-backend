# expects azure_scheme to be passed in from create_router
from typing import Callable, Optional

from fastapi import Security
from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer
from fastapi_azure_auth.user import User

type AuthSchema = Callable[..., Optional[User]]


def create_auth_scheme(azure_scheme: SingleTenantAzureAuthorizationCodeBearer, disable_auth: bool) -> AuthSchema:
    if disable_auth:

        def no_auth() -> Optional[User]:
            return None

        return no_auth
    else:
        # ruff: noqa: B008
        def auth(user: User = Security(azure_scheme)) -> Optional[User]:
            return user

        return auth
