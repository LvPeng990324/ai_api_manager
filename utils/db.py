from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from config import settings


is_sqlite = settings.database_url.startswith("sqlite")

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=5 if is_sqlite else 10,
    max_overflow=10 if is_sqlite else 20,
    pool_recycle=3600,
    connect_args={"check_same_thread": False} if is_sqlite else {},
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
