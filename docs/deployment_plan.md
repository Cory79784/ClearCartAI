# Deployment Plan

## Current Local/VM Deployment

- Backend: Uvicorn + FastAPI on port 8000.
- Frontend: Next.js on port 3000.
- ML execution remains Python-native in the same environment as model dependencies.

## Recommended AWS Path (next phase)

1. Package backend as container image with GPU-compatible base (if GPU inference required).
2. Deploy backend on ECS/EKS or GPU EC2.
3. Deploy frontend on Vercel or S3 + CloudFront.
4. Move in-memory jobs to Redis + worker system (Celery/RQ).
5. Move local storage to S3 for uploads and artifacts.
6. Place API behind ALB + WAF, TLS via ACM.

## Production Hardening Next

- Replace hardcoded admin with managed secrets + user DB.
- Add rate limiting at API gateway/reverse proxy.
- Add persistent job store (PostgreSQL).
- Add object storage lifecycle rules for cleanup.
