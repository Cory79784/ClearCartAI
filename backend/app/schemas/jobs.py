from datetime import datetime
from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    upload_id: str
    file_count: int


class SubmitRequest(BaseModel):
    upload_id: str = Field(min_length=1)


class JobSummary(BaseModel):
    id: str
    status: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class JobDetail(JobSummary):
    output_dir: str
    result: dict | None = None
