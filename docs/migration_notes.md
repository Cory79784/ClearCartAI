# Migration Notes

## What Was Preserved

- Existing ML pipeline and model internals were not rewritten.
- Existing Gradio app remains intact and runnable.
- Existing segmentation artifact format remains unchanged.

## New Components Added

- `backend/` FastAPI service with auth, queue, jobs, admin, health.
- `frontend/` Next.js app for login/upload/jobs/admin workflow.
- `backend/app/ml_bridge/adapter.py` to call existing pipeline.

## Compatibility Notes

- Backend currently uses in-memory job metadata for MVP.
- Backend queue survives process lifetime only (restart clears queue and job memory).
- Admin credentials are intentionally hardcoded in backend config for this phase.
