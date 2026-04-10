import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import get_password_hash
from app.main import app
from app.models.user import User
from app.models.job import Job
from app.models.candidate import Candidate, candidate_skills, Skill
from app.models.application import Application
from app.models.interview import Interview, InterviewFeedback
from app.models.audit_log import AuditLog

try:
    from app.models.offer import Offer
except ImportError:
    pass


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

test_async_session_factory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


async def create_test_user(
    db_session: AsyncSession,
    username: str,
    password: str = "TestPass123",
    role: str = "Interviewer",
    email: str | None = None,
    full_name: str | None = None,
    is_active: bool = True,
) -> User:
    hashed_password = get_password_hash(password)
    user = User(
        username=username,
        hashed_password=hashed_password,
        role=role,
        email=email or f"{username}@test.com",
        full_name=full_name or username.replace("_", " ").title(),
        is_active=is_active,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    return await create_test_user(
        db_session,
        username="test_admin",
        role="System Admin",
        email="admin@test.com",
        full_name="Test Admin",
    )


@pytest_asyncio.fixture
async def hr_user(db_session: AsyncSession) -> User:
    return await create_test_user(
        db_session,
        username="test_hr",
        role="HR Recruiter",
        email="hr@test.com",
        full_name="Test HR Recruiter",
    )


@pytest_asyncio.fixture
async def hiring_manager_user(db_session: AsyncSession) -> User:
    return await create_test_user(
        db_session,
        username="test_manager",
        role="Hiring Manager",
        email="manager@test.com",
        full_name="Test Hiring Manager",
    )


@pytest_asyncio.fixture
async def interviewer_user(db_session: AsyncSession) -> User:
    return await create_test_user(
        db_session,
        username="test_interviewer",
        role="Interviewer",
        email="interviewer@test.com",
        full_name="Test Interviewer",
    )


@pytest_asyncio.fixture
async def super_admin_user(db_session: AsyncSession) -> User:
    return await create_test_user(
        db_session,
        username="test_super_admin",
        role="Super Admin",
        email="superadmin@test.com",
        full_name="Test Super Admin",
    )


async def login_user(client: AsyncClient, username: str, password: str = "TestPass123") -> AsyncClient:
    response = await client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )
    if response.status_code in (302, 303):
        cookies = response.cookies
        for key, value in cookies.items():
            client.cookies.set(key, value)
    return client


@pytest_asyncio.fixture
async def authenticated_admin_client(
    client: AsyncClient,
    admin_user: User,
) -> AsyncClient:
    return await login_user(client, admin_user.username)


@pytest_asyncio.fixture
async def authenticated_hr_client(
    client: AsyncClient,
    hr_user: User,
) -> AsyncClient:
    return await login_user(client, hr_user.username)


@pytest_asyncio.fixture
async def authenticated_manager_client(
    client: AsyncClient,
    hiring_manager_user: User,
) -> AsyncClient:
    return await login_user(client, hiring_manager_user.username)


@pytest_asyncio.fixture
async def authenticated_interviewer_client(
    client: AsyncClient,
    interviewer_user: User,
) -> AsyncClient:
    return await login_user(client, interviewer_user.username)


@pytest_asyncio.fixture
async def sample_job(db_session: AsyncSession, admin_user: User) -> Job:
    job = Job(
        title="Senior Python Developer",
        department="Engineering",
        location="Remote",
        type="Full-Time",
        salary_min=100000,
        salary_max=150000,
        description="We are looking for a senior Python developer.",
        status="Published",
        hiring_manager_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    return job


@pytest_asyncio.fixture
async def sample_candidate(db_session: AsyncSession) -> Candidate:
    candidate = Candidate(
        name="Jane Doe",
        email="jane.doe@example.com",
        phone="+1234567890",
        resume_text="Experienced software engineer with 10 years of Python development.",
        linkedin_url="https://linkedin.com/in/janedoe",
    )
    db_session.add(candidate)
    await db_session.flush()
    await db_session.refresh(candidate)
    return candidate


@pytest_asyncio.fixture
async def sample_application(
    db_session: AsyncSession,
    sample_job: Job,
    sample_candidate: Candidate,
) -> Application:
    application = Application(
        candidate_id=sample_candidate.id,
        job_id=sample_job.id,
        status="Applied",
    )
    db_session.add(application)
    await db_session.flush()
    await db_session.refresh(application)
    return application


@pytest_asyncio.fixture
async def sample_interview(
    db_session: AsyncSession,
    sample_application: Application,
    interviewer_user: User,
) -> Interview:
    from datetime import datetime, timedelta

    interview = Interview(
        application_id=sample_application.id,
        interviewer_id=interviewer_user.id,
        scheduled_at=datetime.utcnow() + timedelta(days=3),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)
    return interview