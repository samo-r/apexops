from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1)
    location: str = Field(min_length=1)
    email: str = Field(min_length=1)


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    location: str | None = Field(default=None, min_length=1)
    email: str | None = Field(default=None, min_length=1)


class OrganizationResponse(BaseModel):
    id: str
    name: str
    location: str
    email: str
