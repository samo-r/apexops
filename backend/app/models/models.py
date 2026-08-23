from beanie import Document, Link
from datetime import datetime

from beanie import Document, Link
from pydantic import Field
from pymongo import ASCENDING, IndexModel
from typing import List

class Organisation(Document):
    name: str 
    location: str
    email: str

    class Settings:
        name = "organisations"  # Collection name in MongoDB

class Role(Document):
    name: str
    permissions: List[str]

    class Settings:
        name = "roles"  # Collection name in MongoDB

class User(Document):
    name: str
    dob: str
    email: str
    pwd_hash: str
    salary: float | None = None
    org: Link[Organisation]
    roles: Link[Role]

    class Settings:
        name = "users"
        indexes = [
            IndexModel(
                [("email", ASCENDING)],
                unique=True,
                name="users_email_unique",
            ),
            IndexModel([("org", ASCENDING)], name="users_org_idx"),
        ]

class Assignment(Document):
    task: str
    status: str = "pending"
    assignee_id: Link[User]
    assigner_id: Link[User]
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "assignments"  # Collection name in MongoDB

