from datetime import timezone

from beanie import PydanticObjectId
import pytest
from pydantic import ValidationError
from pymongo import ASCENDING

from app.models.models import Assignment, Organization, Role, User


def _index_by_name(model: type, name: str) -> dict:
    for index in model.Settings.indexes:
        if index.document["name"] == name:
            return index.document
    raise AssertionError(f"Index {name!r} is not configured")


def _organization() -> Organization:
    return Organization.model_construct(
        name="ApexOps",
        location="Nairobi",
        email="admin@apexops.example",
    )


def _role() -> Role:
    return Role.model_construct(name="operator", permissions=["tasks:assign"])


def _user(org_id: PydanticObjectId, organization: Organization, role: Role) -> User:
    return User.model_construct(
        name="Ada Lovelace",
        dob="1815-12-10",
        email="ada@apexops.example",
        pwd_hash="hashed-password",
        org_id=org_id,
        org=organization,
        roles=role,
    )


def test_organization_and_role_models_initialize_required_fields() -> None:
    organization = _organization()
    role = _role()

    assert organization.name == "ApexOps"
    assert organization.location == "Nairobi"
    assert role.permissions == ["tasks:assign"]


def test_organization_rejects_missing_required_fields() -> None:
    with pytest.raises(ValidationError):
        Organization(name="ApexOps", location="Nairobi")


def test_user_stores_direct_organization_id() -> None:
    org_id = PydanticObjectId()
    user = _user(org_id, _organization(), _role())

    assert user.org_id == org_id
    assert user.salary is None
    assert user.is_active is True


def test_assignment_initializes_defaults_and_direct_organization_id() -> None:
    org_id = PydanticObjectId()
    organization = _organization()
    role = _role()
    user = _user(org_id, organization, role)

    assignment = Assignment.model_construct(
        task="Review operational metrics",
        org_id=org_id,
        assignee_id=user,
        assigner_id=user,
    )

    assert assignment.status == "pending"
    assert assignment.org_id == org_id
    assert assignment.created_at.tzinfo is timezone.utc
    assert assignment.created_at.utcoffset().total_seconds() == 0


def test_unique_indexes_are_declared_for_business_identifiers() -> None:
    organization_name = _index_by_name(Organization, "organizations_name_unique")
    role_name = _index_by_name(Role, "roles_name_unique")
    user_email = _index_by_name(User, "users_email_unique")

    assert organization_name["key"] == {"name": ASCENDING}
    assert organization_name["unique"] is True
    assert role_name["key"] == {"name": ASCENDING}
    assert role_name["unique"] is True
    assert user_email["key"] == {"email": ASCENDING}
    assert user_email["unique"] is True
