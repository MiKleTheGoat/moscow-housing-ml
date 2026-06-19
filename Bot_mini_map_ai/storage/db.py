from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.storage.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSession = async_sessionmaker(engine, expire_on_commit=False)


async def get_session():
    async with AsyncSession() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)