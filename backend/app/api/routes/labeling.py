from pathlib import Path
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.auth import current_user
from app.models.user import User

from app.schemas.labeling import (
    AcceptAllProposedRequest,
    AcceptProposedRequest,
    LabelingLoadRequest,
    LabelingPointRequest,
    LabelingResetRequest,
    LabelingSaveRequest,
    LabelingSkipRequest,
    RejectProposedRequest,
)
from app.services.labeling_service import LabelingService

router = APIRouter(prefix="/labeling", tags=["labeling"])
svc = LabelingService()


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    uploader_name: str = Form(default=""),
    product_name: str = Form(default=""),
    _: User = Depends(current_user),
):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip supported")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
        temp_file.write(await file.read())
        temp_path = Path(temp_file.name)
    try:
        status = svc.upload_and_ingest(
            temp_path,
            uploader_name,
            original_filename=file.filename,
            product_name_override=product_name,
        )
        return {"status": status}
    finally:
        temp_path.unlink(missing_ok=True)


@router.post("/load-next")
def load_next(payload: LabelingLoadRequest, _: User = Depends(current_user)):
    return svc.load_next(payload.labeler_id, payload.session_id)


@router.post("/add-point")
def add_point(payload: LabelingPointRequest, _: User = Depends(current_user)):
    return svc.add_point(payload.session_id, payload.x, payload.y)


@router.post("/reset")
def reset(payload: LabelingResetRequest, _: User = Depends(current_user)):
    return svc.reset(payload.session_id)


@router.post("/skip")
def skip(payload: LabelingSkipRequest, _: User = Depends(current_user)):
    return svc.skip_and_next(payload.session_id, payload.labeler_id, payload.reason)


@router.post("/save")
def save(payload: LabelingSaveRequest, _: User = Depends(current_user)):
    return svc.save_and_next(payload.session_id, payload.packaging, payload.product_name)


@router.get("/proposed")
def get_proposed(
    product_id: Optional[int] = None,
    _: User = Depends(current_user),
):
    return {"proposed": svc.get_proposed(product_id)}


@router.post("/accept")
def accept_proposed(payload: AcceptProposedRequest, _: User = Depends(current_user)):
    return svc.accept_proposed(
        payload.label_id, payload.packaging, payload.product_name, payload.labeler_id
    )


@router.post("/reject")
def reject_proposed(payload: RejectProposedRequest, _: User = Depends(current_user)):
    return svc.reject_proposed(payload.image_id)


@router.post("/accept-all")
def accept_all_proposed(payload: AcceptAllProposedRequest, _: User = Depends(current_user)):
    return svc.accept_all_proposed(
        payload.product_id, payload.packaging, payload.product_name, payload.labeler_id
    )


@router.get("/progress/{product_id}")
def get_progress(product_id: int, _: User = Depends(current_user)):
    from ean_system import db as _db
    return _db.get_product_progress(product_id)
