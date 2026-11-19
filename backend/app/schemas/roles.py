from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    name: str = Field(min_length=1)
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    permissions: list[str] | None = None


class RoleResponse(BaseModel):
    id: str
    name: str
    permissions: list[str]
