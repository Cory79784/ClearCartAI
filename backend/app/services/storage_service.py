import os
import uuid
from pathlib import Path
from fastapi import UploadFile

from app.core.config import settings
from app.utils.paths import upload_path


class StorageService:
    async def save_upload(self, file: UploadFile) -> tuple[str, Path]:
        upload_id = str(uuid.uuid4())
        target = upload_path(upload_id)
        written = 0
        with target.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    out.close()
                    os.remove(target)
                    raise ValueError("Upload too large")
                out.write(chunk)
        return upload_id, target
