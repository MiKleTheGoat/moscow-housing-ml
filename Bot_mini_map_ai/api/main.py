import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.api.routes import parse, train, tasks
from Bot_mini_map_ai.api.routes import predict
from Bot_mini_map_ai.api.admin_routes import router as admin_router


logger = logging.getLogger(__name__)

app = FastAPI(title="Moscow Housing ML API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.MINI_APP_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parse.router,   prefix="/api", tags=["parser"])
app.include_router(train.router,   prefix="/api", tags=["ml"])
app.include_router(predict.router, prefix="/api", tags=["ml"])
app.include_router(tasks.router,   prefix="/api", tags=["tasks"])
app.include_router(admin_router)                  # /admin/*



from Bot_mini_map_ai.storage.db import init_db

@app.on_event("startup")
async def startup():
    await init_db()
    logger.info("API running on %s", settings.ML_API_URL)


@app.get("/health")
async def health():
    return {"status": "ok"}
