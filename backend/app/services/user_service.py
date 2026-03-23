import hashlib
import json
import threading
from pathlib import Path

from app.core.config import settings


class UserService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._file = settings.storage_root / "users.json"
        self._file.parent.mkdir(parents=True, exist_ok=True)
        if not self._file.exists():
            self._write({"users": []})

    def _read(self) -> dict:
        with self._file.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, payload: dict) -> None:
        with self._file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def list_users(self) -> list[dict]:
        data = self._read()
        # Never expose password hashes to API clients.
        return [{"username": u["username"], "role": u.get("role", "user")} for u in data.get("users", [])]

    def create_user(self, username: str, password: str, role: str = "user") -> dict:
        with self._lock:
            data = self._read()
            users = data.get("users", [])
            if username == settings.admin_username or any(u["username"] == username for u in users):
                raise ValueError("Username already exists")
            users.append(
                {
                    "username": username,
                    "password_hash": self._hash_password(password),
                    "role": role,
                }
            )
            data["users"] = users
            self._write(data)
        return {"username": username, "role": role}

    def verify_user(self, username: str, password: str) -> dict | None:
        data = self._read()
        target_hash = self._hash_password(password)
        for u in data.get("users", []):
            if u["username"] == username and u["password_hash"] == target_hash:
                return {"username": u["username"], "role": u.get("role", "user")}
        return None
