import logging
import asyncio

from Bot_mini_map_ai.celery_app import app
from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.parser.playwright import PlaywrightParser


logger = logging.getLogger(__name__)


@app.task(
    bind=True,
    name="Bot_mini_map_ai.tasks.run_train_task",
    max_retries=2,
    default_retry_delay=60,
)
def run_train_task(self, n_trials: int = 20) -> dict:
    logger.info("▶ train | n_trials=%d | task_id=%s", n_trials, self.request.id)
    try:
        from Bot_mini_map_ai.ml.train import train_model
        result = train_model(n_trials=n_trials)
        logger.info("✓ train | MAE=%.0f | R²=%.4f", result.get("mae", 0), result.get("r2_score", 0))
        return result
    except FileNotFoundError as exc:
        logger.error("✗ train | файл данных не найден: %s", exc)
        raise
    except Exception as exc:
        logger.error("✗ train | %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@app.task(
    bind=True,
    name="Bot_mini_map_ai.tasks.run_parse_task",
    max_retries=1,
    default_retry_delay=300,
)
def run_parse_task(self, max_pages: int = None, start_page: int = None) -> dict:
    max_pages = max_pages or settings.PARSER_MAX_PAGES
    logger.info("▶ parse | max_pages=%d | start_page=%s | task_id=%s", max_pages, start_page, self.request.id)
    try:
        parser = PlaywrightParser(
            headless=settings.PARSER_HEADLESS,
            max_concurrent=settings.PARSER_MAX_CONCURRENT,
        )
        asyncio.run(parser.run(max_pages=max_pages, start_page=start_page))
        collected = len(getattr(parser, "results", []))
        logger.info("✓ parse | собрано=%d", collected)
        return {"status": "done", "collected": collected}
    except Exception as exc:
        logger.error("✗ parse | %s", exc, exc_info=True)
        raise self.retry(exc=exc)
