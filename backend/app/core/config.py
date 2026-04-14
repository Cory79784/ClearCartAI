from pathlib import Path
from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "ClearCart Segmentation API"
    api_prefix: str = "/api"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])
    cors_origin_regex: str = r"^https?://[a-zA-Z0-9-]+-3000\.proxy\.runpod\.net$"
    max_upload_bytes: int = 200 * 1024 * 1024
    max_zip_members: int = 500
    max_extracted_bytes: int = 800 * 1024 * 1024
    max_concurrent_jobs: int = 2
    admin_username: str = "admin"
    admin_password: str = "nikhil@123"
    session_secret: str = "change-this-in-production"
    project_root: Path = Path(__file__).resolve().parents[3]
    storage_root: Path = Path(__file__).resolve().parents[2] / "storage"
    frontend_origin: str = "http://localhost:3000"


settings = Settings()
