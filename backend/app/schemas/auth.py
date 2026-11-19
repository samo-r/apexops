from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class JWTPayload(BaseModel):
    """Validated claims carried by an ApexOps access token."""

    model_config = ConfigDict(extra="forbid")

    sub: str = Field(min_length=1)
    org_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    permissions: list[str]
    exp: datetime | None = None
