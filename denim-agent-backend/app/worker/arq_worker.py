from dotenv import load_dotenv
load_dotenv()

from arq.connections import RedisSettings
from app.worker.tasks import run_full_pipeline, run_campaign_from_prompt, run_orchestrator_job
from app.core.config import settings

class WorkerSettings:
    functions = [run_full_pipeline, run_campaign_from_prompt, run_orchestrator_job]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
