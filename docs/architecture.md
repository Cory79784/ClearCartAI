# Architecture

## Repository Findings

- Existing ML inference is centered in `ean_system/pipeline.py` with `ProductSegmentationPipeline`.
- Model loading stays in `ean_system/model_loader.py` and is lazily initialized.
- Gradio UI stays in `tools/label_ui_gradio.py`; callbacks and segmentation flow are preserved.
- Existing output artifacts (`masks`, `cutouts`, `overlays`, `summary.json`, `gallery.jpg`) are preserved.

## Added Production-Oriented Layers

- `backend/app` (FastAPI)
  - Auth endpoints (`/api/auth/*`) with admin login (`admin` / `nikhil@123`).
  - Secure ZIP upload endpoint (`/api/jobs/upload-zip`).
  - Async queue and worker-based job execution (`/api/jobs/submit`).
  - Concurrency control enforced at backend with max 2 active jobs.
  - Admin observability endpoints (`/api/admin/*`).
- `backend/app/ml_bridge/adapter.py`
  - Shared bridge that calls existing `ProductSegmentationPipeline` (no model rewrite).
- `frontend` (Next.js)
  - Login, dashboard, upload, jobs list/detail, and admin pages.

## Data Flow

1. Login -> receives secure HTTP-only cookie session.
2. Upload ZIP -> validated and extracted safely.
3. Submit job -> job enters queue.
4. Worker picks job when slot available (max 2 running).
5. ML bridge runs pipeline and writes outputs.
6. Frontend polls job status and displays result metadata.
