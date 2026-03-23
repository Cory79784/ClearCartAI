from app.services.job_service import JobService
from app.core.queue_manager import QueueManager
from app.services.user_service import UserService


job_service = JobService()
queue_manager = QueueManager(job_service=job_service, workers=2)
user_service = UserService()
