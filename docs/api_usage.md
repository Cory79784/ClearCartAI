# API Usage

Base URL: `http://localhost:8000/api`

## Auth

- `POST /auth/login` body: `{ "username": "admin", "password": "nikhil@123" }`
- `POST /auth/logout`
- `GET /auth/me`

## Health

- `GET /health`
- `GET /health/ready`

## Jobs

- `POST /jobs/upload-zip` (multipart file field: `file`)
- `POST /jobs/submit` body: `{ "upload_id": "..." }`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `GET /jobs/{job_id}/result`
- `DELETE /jobs/{job_id}`

## Admin

- `GET /admin/queue`
- `GET /admin/jobs`
- `GET /admin/system`
