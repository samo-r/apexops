import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.main import health_check, readiness_check


def test_health_returns_ok() -> None:
    assert asyncio.run(health_check()) == {"status": "healthy"}


def test_ready_returns_ok_when_mongo_ping_succeeds() -> None:
    ping = AsyncMock(return_value={"ok": 1})
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                mongo_client=SimpleNamespace(admin=SimpleNamespace(command=ping))
            )
        )
    )

    assert asyncio.run(readiness_check(request)) == {"status": "ready"}
    ping.assert_awaited_once_with("ping")


def test_ready_returns_503_when_mongo_client_missing() -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(readiness_check(request))

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["status"] == "not_ready"
    assert exc_info.value.detail["reason"] == "mongo_unavailable"


def test_ready_returns_503_when_mongo_ping_fails() -> None:
    ping = AsyncMock(side_effect=ConnectionError("mongo unavailable"))
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                mongo_client=SimpleNamespace(admin=SimpleNamespace(command=ping))
            )
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(readiness_check(request))

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["status"] == "not_ready"
    assert exc_info.value.detail["reason"] == "mongo_ping_failed"
