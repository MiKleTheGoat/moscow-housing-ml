import logging
from fastapi import APIRouter
from pydantic import BaseModel
from celery.result import AsyncResult

from Bot_mini_map_ai.celery_app import app

logger = logging.getLogger(__name__)
router = APIRouter()


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: dict | str | None = None
    traceback: str | None = None


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    res = AsyncResult(task_id, app=app)
    
    result_data = None
    if res.ready():
        if res.successful():
            result_data = res.result
        else:
            result_data = str(res.result)
            
    return TaskStatusResponse(
        task_id=task_id,
        status=res.status,
        result=result_data,
        traceback=res.traceback,
    )
