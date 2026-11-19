from beanie import Link, PydanticObjectId
from bson import ObjectId
from fastapi import HTTPException, status

from app.models.models import Organization, Role, User


def parse_object_id(value: str, *, detail: str = "Resource not found") -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return ObjectId(value)


def link_id(link: Link | ObjectId | PydanticObjectId | None) -> str:
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Missing linked resource",
        )
    if isinstance(link, (ObjectId, PydanticObjectId)):
        return str(link)
    ref = getattr(link, "ref", None)
    if ref is not None and getattr(ref, "id", None) is not None:
        return str(ref.id)
    linked_id = getattr(link, "id", None)
    if linked_id is not None:
        return str(linked_id)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Missing linked resource",
    )


async def get_role_or_404(role_id: str) -> Role:
    role = await Role.get(parse_object_id(role_id, detail="Role not found"))
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


async def get_organization_or_404(org_id: str) -> Organization:
    organization = await Organization.get(
        parse_object_id(org_id, detail="Organization not found")
    )
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return organization


def ensure_same_tenant(resource_org_id: ObjectId | PydanticObjectId | str, jwt_org_id: str) -> None:
    if str(resource_org_id) != jwt_org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
