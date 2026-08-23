from contextlib import asynccontextmanager

from beanie import init_beanie
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from app.api.v1 import auth, tasks
from app.core.config import get_settings
from app.models.models import Assignment, Organisation, Role, User

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(settings.mongo_uri)
    await init_beanie(
        database=client[settings.mongo_database],
        document_models=[Organisation, Role, User, Assignment],
    )
    app.state.mongo_client = client

    try:
        yield
    finally:
        client.close()


app = FastAPI(title="ApexOps RBAC Engine", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(tasks.router)