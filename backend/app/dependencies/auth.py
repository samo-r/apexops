import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import ALGORITHM, SECRET_KEY

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")

async def get_current_token_payload(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "org_id", "permissions", "exp"]},
        )
    except jwt.InvalidTokenError:
        raise credentials_error

    permissions = payload.get("permissions")
    if (
        not isinstance(payload.get("sub"), str)
        or not isinstance(payload.get("org_id"), str)
        or not isinstance(permissions, list)
        or not all(isinstance(permission, str) for permission in permissions)
    ):
        raise credentials_error

    return payload

def require_permissions(*required_permissions: str, require_all: bool = True):
    async def dependency(payload: dict = Depends(get_current_token_payload)):
        granted_permissions = set(payload["permissions"])
        required = set(required_permissions)
        authorized = (
            required.issubset(granted_permissions)
            if require_all
            else bool(required & granted_permissions)
        )
        if not authorized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return payload

    return dependency


def require_permission(permission_key: str):
    return require_permissions(permission_key)
