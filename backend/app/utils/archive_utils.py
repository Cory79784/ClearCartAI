from pathlib import Path


def safe_extract_path(base_dir: Path, member_name: str) -> Path:
    target = (base_dir / member_name).resolve()
    if not str(target).startswith(str(base_dir.resolve())):
        raise ValueError("Archive contains unsafe path")
    return target
