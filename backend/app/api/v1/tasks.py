from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.helpers import link_id, parse_object_id
from app.dependencies.auth import get_user_in_tenant, require_permission
from app.models.models import Assignment
from app.schemas.auth import JWTPayload
from app.schemas.tasks import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])


def _to_response(assignment: Assignment) -> TaskResponse:
    return TaskResponse(
        id=str(assignment.id),
        task=assignment.task,
        status=assignment.status,
        org_id=str(assignment.org_id),
        assignee_id=link_id(assignment.assignee_id),
        assigner_id=link_id(assignment.assigner_id),
        created_at=assignment.created_at,
    )


async def _get_assignment_in_tenant(task_id: str, org_id: str) -> Assignment:
    assignment = await Assignment.find_one(
        Assignment.id == parse_object_id(task_id, detail="Task not found"),
        Assignment.org_id == PydanticObjectId(org_id),
    )
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return assignment


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    payload: JWTPayload = Depends(require_permission("tasks:assign")),
):
    assignee = await get_user_in_tenant(body.assignee_id, payload.org_id)
    assigner = await get_user_in_tenant(payload.sub, payload.org_id)

    assignment = Assignment(
        task=body.task,
        org_id=PydanticObjectId(payload.org_id),
        assignee_id=assignee,
        assigner_id=assigner,
    )
    await assignment.insert()
    return _to_response(assignment)


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    payload: JWTPayload = Depends(require_permission("tasks:read")),
):
    assignments = await Assignment.find(
        Assignment.org_id == PydanticObjectId(payload.org_id)
    ).to_list()
    return [_to_response(assignment) for assignment in assignments]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    payload: JWTPayload = Depends(require_permission("tasks:read")),
):
    assignment = await _get_assignment_in_tenant(task_id, payload.org_id)
    return _to_response(assignment)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    body: TaskUpdate,
    payload: JWTPayload = Depends(require_permission("tasks:update")),
):
    assignment = await _get_assignment_in_tenant(task_id, payload.org_id)
    updates = body.model_dump(exclude_unset=True)

    if "assignee_id" in updates:
        assignee_id = updates.pop("assignee_id")
        assignee = await get_user_in_tenant(assignee_id, payload.org_id)
        updates["assignee_id"] = assignee

    if updates:
        await assignment.set(updates)

    refreshed = await _get_assignment_in_tenant(task_id, payload.org_id)
    return _to_response(refreshed)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    payload: JWTPayload = Depends(require_permission("tasks:delete")),
):
    assignment = await _get_assignment_in_tenant(task_id, payload.org_id)
    await assignment.delete()
