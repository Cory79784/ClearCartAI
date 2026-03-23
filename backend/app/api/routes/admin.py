from fastapi import APIRouter, Depends

from app.core.auth import current_user
from app.models.user import User
from app.core.state import job_service, queue_manager, user_service
from app.schemas.admin import CreateUserRequest, UserResponse

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin required")
    return user


@router.get("/queue")
def queue_info(_: User = Depends(require_admin)) -> dict:
    return {"pending_queue_size": queue_manager.queue.qsize(), "active_limit": 2}


@router.get("/jobs")
def all_jobs(_: User = Depends(require_admin)) -> list[dict]:
    return [
        {"id": j.id, "owner": j.owner, "status": j.status, "created_at": j.created_at}
        for j in job_service.list_all()
    ]


@router.get("/system")
def system_info(_: User = Depends(require_admin)) -> dict:
    return {"service": "ok", "max_concurrent_jobs": 2}


@router.get("/users", response_model=list[UserResponse])
def list_users(_: User = Depends(require_admin)) -> list[UserResponse]:
    users = user_service.list_users()
    return [UserResponse(username=u["username"], role=u["role"]) for u in users]


@router.post("/users", response_model=UserResponse)
def create_user(payload: CreateUserRequest, _: User = Depends(require_admin)) -> UserResponse:
    try:
        user = user_service.create_user(payload.username, payload.password, payload.role)
        return UserResponse(username=user["username"], role=user["role"])
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
