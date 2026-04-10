from app.routers.landing import router as landing_router
from app.routers.auth import router as auth_router
from app.routers.jobs import router as jobs_router
from app.routers.candidates import router as candidates_router
from app.routers.applications import router as applications_router
from app.routers.interviews import router as interviews_router
from app.routers.dashboard import router as dashboard_router

__all__ = [
    "landing_router",
    "auth_router",
    "jobs_router",
    "candidates_router",
    "applications_router",
    "interviews_router",
    "dashboard_router",
]