from contextlib import asynccontextmanager

from beanie import init_beanie
from fastapi import FastAPI, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorClient

from app.api.v1 import auth, organizations, roles, tasks, users
from app.core.config import get_settings
from app.models.models import Assignment, Organization, Role, User

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(settings.mongo_uri)
    await init_beanie(
        database=client[settings.mongo_database],
        document_models=[Organization, Role, User, Assignment],
    )
    app.state.mongo_client = client

    try:
        yield
    finally:
        client.close()


app = FastAPI(title="ApexOps RBAC Engine", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(organizations.router)
app.include_router(roles.router)
app.include_router(users.router)
app.include_router(tasks.router)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Liveness probe: process is running."""

    return {"status": "healthy"}


@app.get("/ready", tags=["Health"])
async def readiness_check(request: Request) -> dict[str, str]:
    """Readiness probe: MongoDB accepts a ping."""

    client = getattr(request.app.state, "mongo_client", None)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "reason": "mongo_unavailable"},
        )

    try:
        await client.admin.command("ping")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "reason": "mongo_ping_failed"},
        ) from exc

    return {"status": "ready"}
