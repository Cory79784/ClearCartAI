import asyncio
from .config import settings


inference_semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)
