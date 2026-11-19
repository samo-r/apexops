import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import jwt
import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.api.v1 import auth as auth_routes
from app.api.v1 import roles as role_routes
from app.api.v1 import tasks as task_routes
from app.core import security
from app.schemas.auth import JWTPayload
from app.schemas.roles import RoleUpdate
from app.schemas.tasks import TaskCreate


def _payload(**overrides: object) -> JWTPayload:
    claims: dict[str, object] = {
        "sub": str(ObjectId()),
        "org_id": str(ObjectId()),
        "role": str(ObjectId()),
        "permissions": ["tasks:assign"],
    }
    claims.update(overrides)
    return JWTPayload(**claims)


def test_create_task_persists_assignment_for_same_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_id = ObjectId()
    assigner_id = ObjectId()
    assignee_id = ObjectId()
    assignment_id = ObjectId()

    assigner = SimpleNamespace(id=assigner_id, org_id=org_id)
    assignee = SimpleNamespace(id=assignee_id, org_id=org_id)
    created: list[SimpleNamespace] = []

    async def resolve_user(user_id: str, tenant_id: str, *, fetch_links: bool = False):
        assert tenant_id == str(org_id)
        if user_id == str(assignee_id):
            return assignee
        if user_id == str(assigner_id):
            return assigner
        raise HTTPException(status_code=404, detail="User not found")

    class FakeAssignment:
        def __init__(self, **kwargs):
            self.task = kwargs["task"]
            self.org_id = kwargs["org_id"]
            self.assignee_id = kwargs["assignee_id"]
            self.assigner_id = kwargs["assigner_id"]
            self.status = kwargs.get("status", "pending")
            self.created_at = datetime.now(timezone.utc)
            self.id = None
            created.append(self)

        async def insert(self):
            self.id = assignment_id

    monkeypatch.setattr(task_routes, "get_user_in_tenant", resolve_user)
    monkeypatch.setattr(task_routes, "Assignment", FakeAssignment)

    response = asyncio.run(
        task_routes.create_task(
            TaskCreate(task="Ship tenant isolation", assignee_id=str(assignee_id)),
            payload=_payload(sub=str(assigner_id), org_id=str(org_id)),
        )
    )

    assert len(created) == 1
    assert response.id == str(assignment_id)
    assert response.task == "Ship tenant isolation"
    assert response.status == "pending"
    assert response.org_id == str(org_id)
    assert response.assignee_id == str(assignee_id)
    assert response.assigner_id == str(assigner_id)
    assert response.created_at.tzinfo is not None
    assert response.created_at.utcoffset().total_seconds() == 0


def test_create_task_rejects_cross_tenant_assignee(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_id = ObjectId()

    async def deny_assignee(user_id: str, tenant_id: str, *, fetch_links: bool = False):
        raise HTTPException(status_code=404, detail="User not found")

    monkeypatch.setattr(task_routes, "get_user_in_tenant", deny_assignee)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            task_routes.create_task(
                TaskCreate(task="Cross-tenant attempt", assignee_id=str(ObjectId())),
                payload=_payload(org_id=str(org_id)),
            )
        )

    assert exc_info.value.status_code == 404


def test_role_permission_update_is_reflected_on_next_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_id = ObjectId()
    role_id = ObjectId()
    user_id = ObjectId()
    role = SimpleNamespace(
        id=role_id,
        name="operator",
        permissions=["tasks:assign"],
    )
    user = SimpleNamespace(
        id=user_id,
        org_id=org_id,
        roles=role,
        pwd_hash="stored-password-hash",
        is_active=True,
    )

    async def role_set(updates: dict):
        if "permissions" in updates:
            role.permissions = list(updates["permissions"])

    role.set = role_set
    monkeypatch.setattr(role_routes, "get_role_or_404", AsyncMock(return_value=role))
    monkeypatch.setattr(auth_routes.User, "email", "email", raising=False)
    monkeypatch.setattr(auth_routes.User, "find_one", AsyncMock(return_value=user))
    monkeypatch.setattr(auth_routes, "verify_password", lambda *_: True)

    initial = asyncio.run(
        auth_routes.login(
            SimpleNamespace(username="ada@apexops.example", password="secret")
        )
    )
    initial_payload = JWTPayload.model_validate(
        jwt.decode(
            initial.access_token,
            security.SECRET_KEY,
            algorithms=[security.ALGORITHM],
        )
    )
    assert initial_payload.permissions == ["tasks:assign"]

    updated_role = asyncio.run(
        role_routes.update_role(
            str(role_id),
            RoleUpdate(permissions=["tasks:assign", "users:read"]),
            _payload(permissions=["roles:update"]),
        )
    )
    assert updated_role.permissions == ["tasks:assign", "users:read"]

    refreshed = asyncio.run(
        auth_routes.login(
            SimpleNamespace(username="ada@apexops.example", password="secret")
        )
    )
    refreshed_payload = JWTPayload.model_validate(
        jwt.decode(
            refreshed.access_token,
            security.SECRET_KEY,
            algorithms=[security.ALGORITHM],
        )
    )
    assert refreshed_payload.permissions == ["tasks:assign", "users:read"]
