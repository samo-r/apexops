import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import jwt
import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.api.v1 import auth as auth_routes
from app.core import security
from app.dependencies import auth as auth_dependencies
from app.schemas.auth import JWTPayload


def _payload(**overrides: object) -> JWTPayload:
    claims: dict[str, object] = {
        "sub": str(ObjectId()),
        "org_id": str(ObjectId()),
        "role": str(ObjectId()),
        "permissions": ["tasks:assign"],
    }
    claims.update(overrides)
    return JWTPayload(**claims)


def _login_user(*, is_active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=ObjectId(),
        org_id=ObjectId(),
        roles=SimpleNamespace(id=ObjectId(), permissions=["tasks:assign"]),
        pwd_hash="stored-password-hash",
        is_active=is_active,
    )


def _assert_bearer_unauthorized(error: HTTPException) -> None:
    assert error.status_code == 401
    assert error.headers == {"WWW-Authenticate": "Bearer"}


def _mock_login_lookup(
    monkeypatch: pytest.MonkeyPatch,
    user: SimpleNamespace,
) -> None:
    monkeypatch.setattr(auth_routes.User, "email", "email", raising=False)
    monkeypatch.setattr(auth_routes.User, "find_one", AsyncMock(return_value=user))


def test_login_returns_token_with_typed_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _login_user()
    _mock_login_lookup(monkeypatch, user)
    monkeypatch.setattr(auth_routes, "verify_password", lambda *_: True)

    response = asyncio.run(
        auth_routes.login(SimpleNamespace(username="ada@apexops.example", password="secret"))
    )

    decoded = jwt.decode(
        response.access_token,
        security.SECRET_KEY,
        algorithms=[security.ALGORITHM],
    )
    payload = JWTPayload.model_validate(decoded)

    assert response.token_type == "bearer"
    assert payload.sub == str(user.id)
    assert payload.org_id == str(user.org_id)
    assert payload.role == str(user.roles.id)
    assert payload.permissions == ["tasks:assign"]
    assert payload.exp is not None


def test_login_rejects_invalid_password_with_bearer_challenge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_login_lookup(monkeypatch, _login_user())
    monkeypatch.setattr(auth_routes, "verify_password", lambda *_: False)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            auth_routes.login(
                SimpleNamespace(username="ada@apexops.example", password="wrong-password")
            )
        )

    _assert_bearer_unauthorized(exc_info.value)


def test_login_rejects_inactive_user_with_bearer_challenge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_login_lookup(monkeypatch, _login_user(is_active=False))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            auth_routes.login(SimpleNamespace(username="ada@apexops.example", password="secret"))
        )

    _assert_bearer_unauthorized(exc_info.value)


def test_active_user_token_parses_to_typed_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = security.create_access_token(_payload())
    monkeypatch.setattr(
        auth_dependencies.User,
        "get",
        AsyncMock(return_value=SimpleNamespace(is_active=True)),
    )

    decoded = asyncio.run(auth_dependencies.get_current_token_payload(token))

    assert isinstance(decoded, JWTPayload)
    assert decoded.permissions == ["tasks:assign"]


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda: jwt.encode(
            _payload().model_dump(mode="python")
            | {"exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
            security.SECRET_KEY,
            algorithm=security.ALGORITHM,
        ),
        lambda: security.create_access_token(_payload()) + "tampered",
        lambda: jwt.encode(
            {
                "sub": str(ObjectId()),
                "org_id": str(ObjectId()),
                "permissions": [],
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            security.SECRET_KEY,
            algorithm=security.ALGORITHM,
        ),
    ],
)
def test_invalid_or_expired_tokens_are_rejected(
    token_factory: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        auth_dependencies.User,
        "get",
        AsyncMock(return_value=SimpleNamespace(is_active=True)),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(auth_dependencies.get_current_token_payload(token_factory()))

    _assert_bearer_unauthorized(exc_info.value)


@pytest.mark.parametrize("user", [None, SimpleNamespace(is_active=False)])
def test_deleted_or_inactive_token_subject_is_rejected(
    user: SimpleNamespace | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_dependencies.User, "get", AsyncMock(return_value=user))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            auth_dependencies.get_current_token_payload(
                security.create_access_token(_payload())
            )
        )

    _assert_bearer_unauthorized(exc_info.value)


def test_password_hashing_and_validation_are_safe() -> None:
    password = "correct horse battery staple"
    password_hash = security.hash_password(password)

    assert security.verify_password(password, password_hash) is True
    assert security.verify_password("incorrect", password_hash) is False
    assert security.verify_password(password, "not-a-password-hash") is False
    with pytest.raises(ValueError):
        security.hash_password("")
