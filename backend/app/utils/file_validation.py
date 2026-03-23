from pathlib import Path


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def is_zip_filename_safe(filename: str) -> bool:
    return filename.lower().endswith(".zip")


def is_allowed_image(path: Path) -> bool:
    return path.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS
