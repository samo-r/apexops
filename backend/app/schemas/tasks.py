from datetime import datetime

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    task: str = Field(min_length=1)
    assignee_id: str = Field(min_length=1)


class TaskUpdate(BaseModel):
    task: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, min_length=1)
    assignee_id: str | None = Field(default=None, min_length=1)


class TaskResponse(BaseModel):
    id: str
    task: str
    status: str
    org_id: str
    assignee_id: str
    assigner_id: str
    created_at: datetime
