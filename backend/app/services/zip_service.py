import zipfile
from pathlib import Path

from app.core.config import settings
from app.utils.archive_utils import safe_extract_path
from app.utils.file_validation import is_allowed_image
from app.utils.paths import extract_dir


class ZipService:
    def validate_and_extract(self, upload_id: str, zip_path: Path) -> tuple[Path, int]:
        if zip_path.suffix.lower() != ".zip":
            raise ValueError("Only .zip files are accepted")
        out_dir = extract_dir(upload_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        total_members = 0
        total_bytes = 0
        with zipfile.ZipFile(zip_path, "r") as zf:
            infos = zf.infolist()
            if len(infos) > settings.max_zip_members:
                raise ValueError("Too many files in ZIP")
            for info in infos:
                if info.is_dir():
                    continue
                total_members += 1
                total_bytes += info.file_size
                if total_bytes > settings.max_extracted_bytes:
                    raise ValueError("Extracted data exceeds limit")
                safe_target = safe_extract_path(out_dir, info.filename)
                member_name = Path(info.filename)
                if not is_allowed_image(member_name):
                    continue
                safe_target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, "r") as src, safe_target.open("wb") as dst:
                    dst.write(src.read())
        kept_images = [p for p in out_dir.rglob("*") if p.is_file() and is_allowed_image(p)]
        if not kept_images:
            raise ValueError("ZIP contains no allowed images")
        return out_dir, len(kept_images)
