from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class JobRecord:
    id: str
    owner: str
    upload_id: str
    input_dir: str
    output_dir: str
    status: str = "queued"
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
