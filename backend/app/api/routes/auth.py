from fastapi import APIRouter, Depends, Response, status

from app.core.auth import current_user
from app.core.security import COOKIE_NAME, create_session_token, verify_admin_credentials
from app.core.state import user_service
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response) -> LoginResponse:
    role = ""
    if verify_admin_credentials(payload.username, payload.password):
        role = "admin"
    else:
        user = user_service.verify_user(payload.username, payload.password)
        if not user:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return LoginResponse(ok=False, username="", role="")
        role = user["role"]

    token = create_session_token(payload.username, role=role)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 12,
    )
    return LoginResponse(ok=True, username=payload.username, role=role)


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"ok": True, "username": user.username, "role": user.role}
