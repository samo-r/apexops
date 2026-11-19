from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, status
from starlette.concurrency import run_in_threadpool

from app.api.v1.helpers import get_organization_or_404, get_role_or_404, link_id
from app.core.security import hash_password
from app.dependencies.auth import get_user_in_tenant, require_permission
from app.models.models import User
from app.schemas.auth import JWTPayload
from app.schemas.users import (
    UserAdminResponse,
    UserCreate,
    UserPublicResponse,
    UserUpdate,
    to_admin_user,
    to_public_user,
)

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


def _admin_response(user: User, permissions: list[str]) -> UserAdminResponse:
    return to_admin_user(user, permissions, role_id=link_id(user.roles))


@router.post("", response_model=UserAdminResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    payload: JWTPayload = Depends(require_permission("users:create")),
):
    organization = await get_organization_or_404(payload.org_id)
    role = await get_role_or_404(body.role_id)
    password_hash = await run_in_threadpool(hash_password, body.password)

    user = User(
        name=body.name,
        dob=body.dob,
        email=body.email,
        pwd_hash=password_hash,
        salary=body.salary,
        is_active=body.is_active,
        org_id=PydanticObjectId(payload.org_id),
        org=organization,
        roles=role,
    )
    await user.insert()
    return _admin_response(user, payload.permissions)


@router.get("", response_model=list[UserAdminResponse])
async def list_users(
    payload: JWTPayload = Depends(require_permission("users:read")),
):
    users = await User.find(User.org_id == PydanticObjectId(payload.org_id)).to_list()
    return [_admin_response(user, payload.permissions) for user in users]


@router.get("/{user_id}", response_model=UserPublicResponse)
async def get_user_profile(
    user_id: str,
    payload: JWTPayload = Depends(require_permission("users:read")),
):
    user = await get_user_in_tenant(user_id, payload.org_id, fetch_links=True)
    return to_public_user(user, payload.permissions)


@router.patch("/{user_id}", response_model=UserAdminResponse)
async def update_user(
    user_id: str,
    body: UserUpdate,
    payload: JWTPayload = Depends(require_permission("users:update")),
):
    user = await get_user_in_tenant(user_id, payload.org_id)
    updates = body.model_dump(exclude_unset=True)

    if "password" in updates:
        password = updates.pop("password")
        updates["pwd_hash"] = await run_in_threadpool(hash_password, password)

    if "role_id" in updates:
        role_id = updates.pop("role_id")
        role = await get_role_or_404(role_id)
        updates["roles"] = role

    if updates:
        await user.set(updates)

    refreshed = await get_user_in_tenant(user_id, payload.org_id)
    return _admin_response(refreshed, payload.permissions)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    payload: JWTPayload = Depends(require_permission("users:delete")),
):
    user = await get_user_in_tenant(user_id, payload.org_id)
    await user.delete()
