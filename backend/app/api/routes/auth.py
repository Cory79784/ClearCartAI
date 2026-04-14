from fastapi import APIRouter, Depends, Request, Response, status

from app.core.auth import current_user
from app.core.security import COOKIE_NAME, create_session_token, verify_admin_credentials
from app.core.state import user_service
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _cookie_settings(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
    return forwarded_proto == "https" or request.url.scheme == "https"


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> LoginResponse:
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
    cookie_secure = _cookie_settings(request)

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=cookie_secure,
        samesite="lax",
        max_age=60 * 60 * 12,
    )
    return LoginResponse(ok=True, username=payload.username, role=role)


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    cookie_secure = _cookie_settings(request)
    response.delete_cookie(COOKIE_NAME, secure=cookie_secure, samesite="lax")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"ok": True, "username": user.username, "role": user.role}
