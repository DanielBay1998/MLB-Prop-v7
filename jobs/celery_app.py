from celery import Celery

from app.config import settings

celery_app = Celery("mlb_prop_predictor", broker=settings.redis_url, backend=settings.result_backend)
celery_app.conf.update(task_track_started=True, timezone="UTC")
