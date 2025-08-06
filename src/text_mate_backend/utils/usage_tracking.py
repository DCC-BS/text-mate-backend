import hashlib
import hmac

from fastapi_azure_auth.user import User


def get_pseudonymized_user_id(user: User, secret_key: str) -> str:
    """
    Generates a consistent, one-way pseudonym for a given user ID.
    """
    user_id = user.oid or user.sub
    if user_id is None:
        raise ValueError("User ID (oid or sub) not found in user object")
    message = user_id.encode("utf-8")
    if not secret_key or secret_key == "none":
        raise ValueError("HMAC secret is not set")
    signature = hmac.new(secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return signature
