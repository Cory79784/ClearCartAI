import os
from pathlib import Path
from pydantic import BaseModel, Field


def _csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    values = [item.strip() for item in raw.split(",")]
    return [item for item in values if item]


class Settings(BaseModel):
    app_name: str = "ClearCart Segmentation API"
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    cors_origins: list[str] = Field(
        default_factory=lambda: _csv_env("CORS_ORIGINS", ["http://localhost:3000", "http://127.0.0.1:3000"])
    )
    cors_origin_regex: str = os.getenv(
        "CORS_ORIGIN_REGEX",
        r"^https?://[a-zA-Z0-9-]+-3000\.proxy\.runpod\.net$",
    )
    max_upload_bytes: int = 200 * 1024 * 1024
    max_zip_members: int = 500
    max_extracted_bytes: int = 800 * 1024 * 1024
    max_concurrent_jobs: int = 2
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "nikhil@123")
    session_secret: str = os.getenv("SESSION_SECRET", "change-this-in-production")
    project_root: Path = Path(__file__).resolve().parents[3]
    storage_root: Path = Path(__file__).resolve().parents[2] / "storage"
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")


settings = Settings()
