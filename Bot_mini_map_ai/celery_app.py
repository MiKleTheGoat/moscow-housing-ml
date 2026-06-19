from celery import Celery
from celery.schedules import crontab

from Bot_mini_map_ai.config.settings import settings

app = Celery(
    "bot_mini_map",
    broker=settings.REDIS_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["Bot_mini_map_ai.tasks"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Moscow",
    enable_utc=True,
    result_expires=86400,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

app.conf.beat_schedule = {
    "weekly-parse": {
        "task": "Bot_mini_map_ai.tasks.run_parse_task",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),
    },
    "weekly-train": {
        "task": "Bot_mini_map_ai.tasks.run_train_task",
        "schedule": crontab(hour=5, minute=0, day_of_week=0),
        "args": [20],
    },
}
