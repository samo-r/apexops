import jwt
from beanie import PydanticObjectId
from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import ALGORITHM, SECRET_KEY
from app.models.models import User
from app.schemas.auth import JWTPayload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _not_found(detail: str = "User not found") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


async def get_current_token_payload(
    token: str = Depends(oauth2_scheme),
) -> JWTPayload:
    credentials_error = _credentials_error()

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "org_id", "role", "permissions", "exp"]},
        )
    except jwt.InvalidTokenError:
        raise credentials_error from None

    try:
        validated_payload = JWTPayload.model_validate(payload)
    except ValueError:
        raise credentials_error from None

    if not ObjectId.is_valid(validated_payload.sub):
        raise credentials_error

    user = await User.get(ObjectId(validated_payload.sub))
    if user is None or not user.is_active:
        raise credentials_error

    return validated_payload


def require_permissions(*required_permissions: str, require_all: bool = True):
    """Return a FastAPI dependency that enforces one or more JWT permission claims."""

    async def dependency(payload: JWTPayload = Depends(get_current_token_payload)) -> JWTPayload:
        granted_permissions = set(payload.permissions)
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
    """Reusable single-permission FastAPI dependency factory."""

    return require_permissions(permission_key)


async def get_user_in_tenant(
    user_id: str,
    org_id: str,
    *,
    fetch_links: bool = False,
) -> User:
    """Load a user only when the document belongs to the JWT tenant."""

    if not ObjectId.is_valid(user_id) or not ObjectId.is_valid(org_id):
        raise _not_found()

    user = await User.find_one(
        User.id == ObjectId(user_id),
        User.org_id == PydanticObjectId(org_id),
        fetch_links=fetch_links,
    )
    if user is None:
        raise _not_found()

    return user
