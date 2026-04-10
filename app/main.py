import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.database import async_session_factory, create_all_tables
from app.routers.landing import router as landing_router
from app.routers.auth import router as auth_router
from app.routers.jobs import router as jobs_router
from app.routers.candidates import router as candidates_router
from app.routers.applications import router as applications_router
from app.routers.interviews import router as interviews_router
from app.routers.dashboard import router as dashboard_router

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting TalentFlow ATS application...")

    await create_all_tables()
    logger.info("Database tables created/verified.")

    from app.services.auth_service import seed_default_admin

    async with async_session_factory() as session:
        try:
            await seed_default_admin(session)
        except Exception:
            logger.exception("Failed to seed default admin user")

    logger.info("TalentFlow ATS startup complete.")
    yield
    logger.info("Shutting down TalentFlow ATS application.")


app = FastAPI(
    title="TalentFlow ATS",
    description="Applicant Tracking System built with FastAPI",
    version="1.0.0",
    lifespan=lifespan,
)

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
else:
    logger.warning("Static files directory not found at %s", static_dir)

app.include_router(landing_router)
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(candidates_router)
app.include_router(applications_router)
app.include_router(interviews_router)
app.include_router(dashboard_router)