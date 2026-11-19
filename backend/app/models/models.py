from datetime import datetime, timezone

from beanie import Document, Link, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel
from typing import List


class Organization(Document):
    name: str
    location: str
    email: str

    class Settings:
        name = "organisations"
        indexes = [
            IndexModel(
                [("name", ASCENDING)],
                unique=True,
                name="organizations_name_unique",
            ),
        ]


class Role(Document):
    name: str
    permissions: List[str]

    class Settings:
        name = "roles"
        indexes = [
            IndexModel(
                [("name", ASCENDING)],
                unique=True,
                name="roles_name_unique",
            ),
        ]


class User(Document):
    name: str
    dob: str
    email: str
    pwd_hash: str
    salary: float | None = None
    is_active: bool = True
    org_id: PydanticObjectId
    org: Link[Organization]
    roles: Link[Role]

    class Settings:
        name = "users"
        indexes = [
            IndexModel(
                [("email", ASCENDING)],
                unique=True,
                name="users_email_unique",
            ),
            IndexModel([("org_id", ASCENDING)], name="users_org_id_idx"),
        ]


class Assignment(Document):
    task: str
    status: str = "pending"
    org_id: PydanticObjectId
    assignee_id: Link[User]
    assigner_id: Link[User]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "assignments"
        indexes = [
            IndexModel([("org_id", ASCENDING)], name="assignments_org_id_idx"),
        ]

