from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_all_tables():
    from app.models.user import User  # noqa: F401
    from app.models.job import Job  # noqa: F401
    from app.models.candidate import Candidate, candidate_skills  # noqa: F401
    from app.models.application import Application  # noqa: F401
    from app.models.interview import Interview, InterviewFeedback  # noqa: F401
    from app.models.audit_log import AuditLog  # noqa: F401

    try:
        from app.models.offer import Offer  # noqa: F401
    except ImportError:
        pass

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)