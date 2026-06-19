import logging
from fastapi import APIRouter
from pydantic import BaseModel

from Bot_mini_map_ai.parser.resumer import ParseResumer
from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.tasks import run_parse_task

logger = logging.getLogger(__name__)
router = APIRouter()


class ParseResponse(BaseModel):
    status: str
    last_page: int
    offers_collected: int
    task_id: str | None = None


@router.post("/parse", response_model=ParseResponse)
async def start_parse():
    resumer = ParseResumer()
    start_page = resumer.last_page if resumer.has_saved_state() else settings.PARSER_START_PAGE

    logger.info("Запуск парсинга. Отправка задачи в Celery с %d страницы...", start_page)
    task = run_parse_task.delay(start_page=start_page)

    return ParseResponse(
        status="queued",
        last_page=start_page,
        offers_collected=resumer.offers_collected,
        task_id=task.id,
    )


@router.get("/parse/status", response_model=ParseResponse)
async def parse_status():
    resumer = ParseResumer()
    return ParseResponse(
        status="pending" if resumer.has_saved_state() else "idle",
        last_page=resumer.last_page,
        offers_collected=resumer.offers_collected,
    )
