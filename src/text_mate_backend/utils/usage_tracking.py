from fastapi_azure_auth.user import User


def get_user_id(user: User | None) -> str | None:
    """
    Extract a stable user identifier from an Azure user object.

    Returns None for unauthenticated requests; the UsageTrackingService
    pseudonymizes None as "unknown".
    """
    if user is None:
        return None
    return user.oid or user.sub
