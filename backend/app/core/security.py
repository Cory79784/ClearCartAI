import hashlib
import hmac
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import settings


COOKIE_NAME = "cc_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 12


def verify_admin_credentials(username: str, password: str) -> bool:
    u_ok = hmac.compare_digest(username.encode(), settings.admin_username.encode())
    p_ok = hmac.compare_digest(
        hashlib.sha256(password.encode()).hexdigest(),
        hashlib.sha256(settings.admin_password.encode()).hexdigest(),
    )
    return u_ok and p_ok


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt="clearcart-auth")


def create_session_token(username: str, role: str = "admin") -> str:
    return _serializer().dumps({"username": username, "role": role})


def parse_session_token(token: str) -> dict | None:
    try:
        return _serializer().loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except BadSignature:
        return None
