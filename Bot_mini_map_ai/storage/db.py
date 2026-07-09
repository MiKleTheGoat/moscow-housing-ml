import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.storage.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
AsyncSession = AsyncSessionLocal

_db_initialized = False
_db_init_lock = asyncio.Lock()


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    global _db_initialized
    if _db_initialized:
        return
    async with _db_init_lock:
        if _db_initialized:
            return
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _db_initialized = True