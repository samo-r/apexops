from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.helpers import get_organization_or_404
from app.dependencies.auth import require_permission
from app.models.models import Organization
from app.schemas.auth import JWTPayload
from app.schemas.organizations import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


def _to_response(organization: Organization) -> OrganizationResponse:
    return OrganizationResponse(
        id=str(organization.id),
        name=organization.name,
        location=organization.location,
        email=organization.email,
    )


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreate,
    _: JWTPayload = Depends(require_permission("organizations:create")),
):
    organization = Organization(**body.model_dump())
    await organization.insert()
    return _to_response(organization)


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    payload: JWTPayload = Depends(require_permission("organizations:read")),
):
    organization = await get_organization_or_404(payload.org_id)
    return [_to_response(organization)]


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: str,
    payload: JWTPayload = Depends(require_permission("organizations:read")),
):
    if org_id != payload.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    organization = await get_organization_or_404(org_id)
    return _to_response(organization)


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: str,
    body: OrganizationUpdate,
    payload: JWTPayload = Depends(require_permission("organizations:update")),
):
    if org_id != payload.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    organization = await get_organization_or_404(org_id)
    updates = body.model_dump(exclude_unset=True)
    if updates:
        await organization.set(updates)
    return _to_response(organization)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: str,
    payload: JWTPayload = Depends(require_permission("organizations:delete")),
):
    if org_id != payload.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    organization = await get_organization_or_404(org_id)
    await organization.delete()
