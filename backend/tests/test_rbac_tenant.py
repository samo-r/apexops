import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.api.v1 import users as user_routes
from app.dependencies import auth as auth_dependencies
from app.schemas.auth import JWTPayload


def _payload(**overrides: object) -> JWTPayload:
    claims: dict[str, object] = {
        "sub": str(ObjectId()),
        "org_id": str(ObjectId()),
        "role": str(ObjectId()),
        "permissions": ["users:read"],
    }
    claims.update(overrides)
    return JWTPayload(**claims)


def test_require_permission_denies_missing_claim() -> None:
    dependency = auth_dependencies.require_permission("tasks:assign")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(dependency(payload=_payload(permissions=["users:read"])))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Insufficient permissions"


def test_require_permission_allows_matching_claim() -> None:
    dependency = auth_dependencies.require_permission("users:read")
    payload = _payload(permissions=["users:read", "salary:read_raw"])

    result = asyncio.run(dependency(payload=payload))

    assert result is payload


def test_get_user_in_tenant_queries_by_id_and_org_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_id = ObjectId()
    user_id = ObjectId()
    stored_user = SimpleNamespace(
        id=user_id,
        org_id=org_id,
        name="Ada Lovelace",
        email="ada@apexops.example",
        salary=8500.0,
    )
    find_one = AsyncMock(return_value=stored_user)
    monkeypatch.setattr(auth_dependencies.User, "id", "id", raising=False)
    monkeypatch.setattr(auth_dependencies.User, "org_id", "org_id", raising=False)
    monkeypatch.setattr(auth_dependencies.User, "find_one", find_one)

    user = asyncio.run(
        auth_dependencies.get_user_in_tenant(str(user_id), str(org_id), fetch_links=True)
    )

    assert user is stored_user
    assert find_one.await_count == 1
    args, kwargs = find_one.await_args
    assert len(args) == 2
    assert kwargs["fetch_links"] is True


def test_get_user_in_tenant_rejects_invalid_object_id() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            auth_dependencies.get_user_in_tenant("not-an-object-id", str(ObjectId()))
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "User not found"


def test_get_user_in_tenant_hides_cross_tenant_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_dependencies.User, "id", "id", raising=False)
    monkeypatch.setattr(auth_dependencies.User, "org_id", "org_id", raising=False)
    monkeypatch.setattr(auth_dependencies.User, "find_one", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            auth_dependencies.get_user_in_tenant(str(ObjectId()), str(ObjectId()))
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "User not found"


def test_get_user_profile_denies_missing_permission() -> None:
    payload = _payload(permissions=["tasks:assign"])
    dependency = auth_dependencies.require_permission("users:read")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(dependency(payload=payload))

    assert exc_info.value.status_code == 403


def test_get_user_profile_returns_same_tenant_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_id = ObjectId()
    user_id = ObjectId()
    stored_user = SimpleNamespace(
        id=user_id,
        org_id=org_id,
        name="Ada Lovelace",
        email="ada@apexops.example",
        salary=8500.0,
    )
    monkeypatch.setattr(
        user_routes,
        "get_user_in_tenant",
        AsyncMock(return_value=stored_user),
    )

    response = asyncio.run(
        user_routes.get_user_profile(
            str(user_id),
            payload=_payload(org_id=str(org_id), permissions=["users:read"]),
        )
    )

    assert response.user_id == str(user_id)
    assert response.name == "Ada Lovelace"
    assert response.email == "ada@apexops.example"
    assert response.salary == "$•••••"


def test_get_user_profile_cross_tenant_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def deny_cross_tenant(user_id: str, org_id: str, *, fetch_links: bool = False):
        raise HTTPException(status_code=404, detail="User not found")

    monkeypatch.setattr(user_routes, "get_user_in_tenant", deny_cross_tenant)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            user_routes.get_user_profile(
                str(ObjectId()),
                payload=_payload(permissions=["users:read"]),
            )
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "User not found"
