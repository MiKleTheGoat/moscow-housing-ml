import logging
from fastapi import APIRouter
from pydantic import BaseModel

from Bot_mini_map_ai.tasks import run_train_task

logger = logging.getLogger(__name__)
router = APIRouter()


class TrainResponse(BaseModel):
    status: str
    task_id: str
    message: str


@router.post("/train", response_model=TrainResponse)
async def start_training():
    logger.info("Запрос на обучение модели. Отправка задачи в Celery...")
    task = run_train_task.delay(n_trials=20)
    return TrainResponse(
        status="queued",
        task_id=task.id,
        message="Обучение модели успешно запущено в Celery",
    )
