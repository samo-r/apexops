from pydantic import BaseModel, ConfigDict, Field

from app.models.models import User

SALARY_READ_RAW_PERMISSION = "salary:read_raw"
MASKED_SALARY = "$•••••"


class UserCreate(BaseModel):
    name: str = Field(min_length=1)
    dob: str = Field(min_length=1)
    email: str = Field(min_length=1)
    password: str = Field(min_length=8)
    salary: float | None = None
    role_id: str = Field(min_length=1)
    is_active: bool = True


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    dob: str | None = Field(default=None, min_length=1)
    email: str | None = Field(default=None, min_length=1)
    password: str | None = Field(default=None, min_length=8)
    salary: float | None = None
    role_id: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None


class UserPublicResponse(BaseModel):
    """Public-facing user profile with field-level salary masking."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    name: str
    email: str
    salary: str


class UserAdminResponse(BaseModel):
    """Admin user view with operational metadata and masked salary."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    dob: str
    email: str
    salary: str
    is_active: bool
    org_id: str
    role_id: str


def format_salary(salary: float | None, permissions: list[str]) -> str:
    """Return raw currency text only when the JWT grants salary:read_raw."""

    if SALARY_READ_RAW_PERMISSION in permissions and salary is not None:
        return f"${salary:,.2f}"
    return MASKED_SALARY


def to_public_user(user: User, permissions: list[str]) -> UserPublicResponse:
    return UserPublicResponse(
        user_id=str(user.id),
        name=user.name,
        email=user.email,
        salary=format_salary(user.salary, permissions),
    )


def to_admin_user(user: User, permissions: list[str], *, role_id: str) -> UserAdminResponse:
    return UserAdminResponse(
        id=str(user.id),
        name=user.name,
        dob=user.dob,
        email=user.email,
        salary=format_salary(user.salary, permissions),
        is_active=user.is_active,
        org_id=str(user.org_id),
        role_id=role_id,
    )
