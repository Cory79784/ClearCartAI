import uuid
from datetime import datetime

from app.models.job import JobRecord
from app.utils.paths import extract_dir, job_output_dir


class JobService:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    def create_job(self, upload_id: str, owner: str) -> JobRecord:
        job_id = str(uuid.uuid4())
        rec = JobRecord(
            id=job_id,
            owner=owner,
            upload_id=upload_id,
            input_dir=str(extract_dir(upload_id)),
            output_dir=str(job_output_dir(job_id)),
            status="queued",
        )
        self._jobs[job_id] = rec
        return rec

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    def list_for_owner(self, owner: str) -> list[JobRecord]:
        return [j for j in self._jobs.values() if j.owner == owner]

    def list_all(self) -> list[JobRecord]:
        return list(self._jobs.values())

    def mark_running(self, job_id: str) -> None:
        rec = self._jobs[job_id]
        rec.status = "running"
        rec.started_at = datetime.utcnow()

    def mark_completed(self, job_id: str, result: dict) -> None:
        rec = self._jobs[job_id]
        rec.status = "completed"
        rec.result = result
        rec.completed_at = datetime.utcnow()

    def mark_failed(self, job_id: str, error: str) -> None:
        rec = self._jobs[job_id]
        rec.status = "failed"
        rec.error = error
        rec.completed_at = datetime.utcnow()
