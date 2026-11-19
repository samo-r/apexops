import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from app.api.v1 import users as user_routes
from app.schemas.auth import JWTPayload
from app.schemas.users import (
    MASKED_SALARY,
    UserAdminResponse,
    UserPublicResponse,
    format_salary,
    to_admin_user,
    to_public_user,
)


def _payload(**overrides: object) -> JWTPayload:
    claims: dict[str, object] = {
        "sub": str(ObjectId()),
        "org_id": str(ObjectId()),
        "role": str(ObjectId()),
        "permissions": ["users:read"],
    }
    claims.update(overrides)
    return JWTPayload(**claims)


def _user(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": ObjectId(),
        "name": "Ada Lovelace",
        "dob": "1815-12-10",
        "email": "ada@apexops.example",
        "salary": 8500.0,
        "is_active": True,
        "org_id": ObjectId(),
        "roles": SimpleNamespace(id=ObjectId()),
        "pwd_hash": "should-never-leak",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_format_salary_returns_raw_when_permission_present() -> None:
    assert format_salary(8500.0, ["salary:read_raw"]) == "$8,500.00"


def test_format_salary_masks_when_permission_missing() -> None:
    assert format_salary(8500.0, ["users:read"]) == MASKED_SALARY


def test_public_and_admin_dtos_never_expose_password_hash() -> None:
    user = _user()
    public = to_public_user(user, ["users:read"])
    admin = to_admin_user(user, ["users:read"], role_id=str(user.roles.id))

    assert isinstance(public, UserPublicResponse)
    assert isinstance(admin, UserAdminResponse)
    assert "pwd_hash" not in public.model_dump()
    assert "pwd_hash" not in admin.model_dump()
    assert public.salary == MASKED_SALARY
    assert admin.salary == MASKED_SALARY


def test_get_user_profile_returns_raw_salary_with_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _user(salary=8500.0)
    monkeypatch.setattr(
        user_routes,
        "get_user_in_tenant",
        AsyncMock(return_value=user),
    )

    response = asyncio.run(
        user_routes.get_user_profile(
            str(user.id),
            payload=_payload(
                org_id=str(user.org_id),
                permissions=["users:read", "salary:read_raw"],
            ),
        )
    )

    assert response.salary == "$8,500.00"
    assert response.user_id == str(user.id)


def test_get_user_profile_masks_salary_without_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _user(salary=8500.0)
    monkeypatch.setattr(
        user_routes,
        "get_user_in_tenant",
        AsyncMock(return_value=user),
    )

    response = asyncio.run(
        user_routes.get_user_profile(
            str(user.id),
            payload=_payload(org_id=str(user.org_id), permissions=["users:read"]),
        )
    )

    assert response.salary == MASKED_SALARY
