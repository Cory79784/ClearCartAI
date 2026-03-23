from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.auth import current_user
from app.models.user import User
from app.schemas.jobs import JobDetail, JobSummary, SubmitRequest, UploadResponse
from app.services.storage_service import StorageService
from app.services.zip_service import ZipService
from app.utils.file_validation import is_zip_filename_safe
from app.core.state import job_service, queue_manager

router = APIRouter(prefix="/jobs", tags=["jobs"])
storage_service = StorageService()
zip_service = ZipService()


uploads_index: dict[str, dict] = {}


@router.post("/upload-zip", response_model=UploadResponse)
async def upload_zip(file: UploadFile = File(...), user: User = Depends(current_user)) -> UploadResponse:
    if not file.filename or not is_zip_filename_safe(file.filename):
        raise HTTPException(status_code=400, detail="Only ZIP upload is allowed")
    if file.content_type not in {"application/zip", "application/x-zip-compressed", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Invalid MIME type for ZIP")
    upload_id, zip_path = await storage_service.save_upload(file)
    extracted_dir, file_count = zip_service.validate_and_extract(upload_id, zip_path)
    uploads_index[upload_id] = {"owner": user.username, "path": str(extracted_dir), "file_count": file_count}
    return UploadResponse(upload_id=upload_id, file_count=file_count)


@router.post("/submit", response_model=JobSummary)
async def submit(payload: SubmitRequest, user: User = Depends(current_user)) -> JobSummary:
    upload = uploads_index.get(payload.upload_id)
    if not upload or upload["owner"] != user.username:
        raise HTTPException(status_code=404, detail="Upload not found")
    rec = job_service.create_job(payload.upload_id, user.username)
    await queue_manager.enqueue(rec.id)
    return JobSummary(
        id=rec.id, status=rec.status, created_at=rec.created_at, started_at=rec.started_at, completed_at=rec.completed_at, error=rec.error
    )


@router.get("", response_model=list[JobSummary])
def list_jobs(user: User = Depends(current_user)) -> list[JobSummary]:
    jobs = job_service.list_for_owner(user.username)
    return [JobSummary(id=j.id, status=j.status, created_at=j.created_at, started_at=j.started_at, completed_at=j.completed_at, error=j.error) for j in jobs]


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: str, user: User = Depends(current_user)) -> JobDetail:
    j = job_service.get(job_id)
    if not j or j.owner != user.username:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobDetail(
        id=j.id,
        status=j.status,
        created_at=j.created_at,
        started_at=j.started_at,
        completed_at=j.completed_at,
        error=j.error,
        output_dir=j.output_dir,
        result=j.result,
    )


@router.get("/{job_id}/result")
def get_result(job_id: str, user: User = Depends(current_user)) -> dict:
    j = job_service.get(job_id)
    if not j or j.owner != user.username:
        raise HTTPException(status_code=404, detail="Job not found")
    if j.status != "completed":
        raise HTTPException(status_code=409, detail=f"Job not completed (status={j.status})")
    return {"job_id": j.id, "result": j.result}


@router.delete("/{job_id}")
def delete_job(job_id: str, user: User = Depends(current_user)) -> dict:
    j = job_service.get(job_id)
    if not j or j.owner != user.username:
        raise HTTPException(status_code=404, detail="Job not found")
    j.status = "cancelled"
    return {"ok": True}
