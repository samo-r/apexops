from fastapi import APIRouter, Depends, status

from app.api.v1.helpers import get_role_or_404
from app.dependencies.auth import require_permission
from app.models.models import Role
from app.schemas.auth import JWTPayload
from app.schemas.roles import RoleCreate, RoleResponse, RoleUpdate

router = APIRouter(prefix="/api/v1/roles", tags=["Roles"])


def _to_response(role: Role) -> RoleResponse:
    return RoleResponse(
        id=str(role.id),
        name=role.name,
        permissions=list(role.permissions),
    )


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    body: RoleCreate,
    _: JWTPayload = Depends(require_permission("roles:create")),
):
    role = Role(name=body.name, permissions=list(body.permissions))
    await role.insert()
    return _to_response(role)


@router.get("", response_model=list[RoleResponse])
async def list_roles(
    _: JWTPayload = Depends(require_permission("roles:read")),
):
    roles = await Role.find_all().to_list()
    return [_to_response(role) for role in roles]


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: str,
    _: JWTPayload = Depends(require_permission("roles:read")),
):
    role = await get_role_or_404(role_id)
    return _to_response(role)


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    body: RoleUpdate,
    _: JWTPayload = Depends(require_permission("roles:update")),
):
    role = await get_role_or_404(role_id)
    updates = body.model_dump(exclude_unset=True)
    if updates:
        await role.set(updates)
    return _to_response(role)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: str,
    _: JWTPayload = Depends(require_permission("roles:delete")),
):
    role = await get_role_or_404(role_id)
    await role.delete()
