# Developer Guide

## Backend Run

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Frontend Run

```bash
cd frontend
npm install
npm run dev
```

Set frontend API base if needed:

```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000/api
```

## Existing Gradio Run (unchanged)

```bash
python tools/label_ui_gradio.py
```

or with ngrok public mode:

```bash
python tools/label_ui_gradio.py --public
```

## Key Security Behavior

- ZIP-only upload, file size limits, archive member limits.
- Zip-slip prevention during extraction.
- Allowed extracted file types restricted to image extensions.
- Auth required for upload, submit, and job endpoints.
- Admin-only endpoints isolated under `/api/admin/*`.
