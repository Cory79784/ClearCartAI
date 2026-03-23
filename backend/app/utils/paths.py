from pathlib import Path
from app.core.config import settings


def ensure_storage_dirs() -> None:
    for d in ["uploads", "extracted", "jobs"]:
        (settings.storage_root / d).mkdir(parents=True, exist_ok=True)


def upload_path(upload_id: str) -> Path:
    return settings.storage_root / "uploads" / f"{upload_id}.zip"


def extract_dir(upload_id: str) -> Path:
    return settings.storage_root / "extracted" / upload_id


def job_output_dir(job_id: str) -> Path:
    return settings.storage_root / "jobs" / job_id
