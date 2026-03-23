import asyncio
import logging

from app.core.concurrency import inference_semaphore
from app.services.inference_service import InferenceService
from app.services.job_service import JobService

logger = logging.getLogger(__name__)


class QueueManager:
    def __init__(self, job_service: JobService, workers: int = 2) -> None:
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.job_service = job_service
        self.inference_service = InferenceService()
        self.workers = workers
        self.tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        for idx in range(self.workers):
            self.tasks.append(asyncio.create_task(self._worker_loop(idx)))

    async def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def enqueue(self, job_id: str) -> None:
        await self.queue.put(job_id)

    async def _worker_loop(self, worker_id: int) -> None:
        while True:
            job_id = await self.queue.get()
            try:
                async with inference_semaphore:
                    self.job_service.mark_running(job_id)
                    rec = self.job_service.get(job_id)
                    if rec is None:
                        continue
                    result = await asyncio.to_thread(
                        self.inference_service.run, rec.input_dir, rec.output_dir
                    )
                    self.job_service.mark_completed(job_id, result)
            except Exception as exc:
                logger.exception("Job failed: %s", job_id)
                self.job_service.mark_failed(job_id, str(exc))
            finally:
                self.queue.task_done()
