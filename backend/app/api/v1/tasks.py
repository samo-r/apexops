from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_token_payload, require_permission
from app.models.models import User
from app.schemas.auth import UserProfileResponse

router = APIRouter(prefix="/api/v1", tags=["Protected Resources"])

@router.post("/tasks", dependencies=[Depends(require_permission("tasks:assign"))])
async def create_task(task_data: dict):
    return {"message": "Task created successfully", "task_data": task_data}

@router.get(
    "/users/{user_id}",
    response_model=UserProfileResponse,
    dependencies=[Depends(require_permission("users:read"))],
)
async def get_user_profile(
    user_id: str,
    payload: dict = Depends(get_current_token_payload)
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user = await User.get(ObjectId(user_id), fetch_links=True)
    if user is None or str(user.org.id) != payload["org_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    has_raw_salary_permission = "salary:read_raw" in payload["permissions"]
    masked_salary = "$•••••"
    if has_raw_salary_permission and user.salary is not None:
        masked_salary = f"${user.salary:,.2f}"

    return UserProfileResponse(
        user_id=str(user.id),
        name=user.name,
        email=user.email,
        salary=masked_salary,
    )