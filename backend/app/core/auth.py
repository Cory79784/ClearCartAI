from fastapi import Cookie, Depends, HTTPException, status

from app.models.user import User
from .security import COOKIE_NAME, parse_session_token


def current_user(cc_session: str | None = Cookie(default=None)) -> User:
    if not cc_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = parse_session_token(cc_session)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return User(username=payload["username"], role=payload.get("role", "admin"))


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user
