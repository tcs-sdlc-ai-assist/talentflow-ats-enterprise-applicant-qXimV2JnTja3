import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import require_login
from app.models.user import User
from app.services.dashboard_service import DashboardService

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/dashboard")
@router.get("/dashboard/")
async def dashboard_page(
    request: Request,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    dashboard_service = DashboardService(db)

    role = current_user.role

    if role == "Interviewer":
        dashboard_data = await dashboard_service.get_interviewer_dashboard(current_user.id)
        return templates.TemplateResponse(
            request,
            "dashboard/index.html",
            context={
                "user": current_user,
                "metrics": dashboard_data.get("metrics", {}),
                "upcoming_interviews": dashboard_data.get("upcoming_interviews", []),
            },
        )

    if role == "Hiring Manager":
        dashboard_data = await dashboard_service.get_hiring_manager_dashboard(current_user.id)
        return templates.TemplateResponse(
            request,
            "dashboard/index.html",
            context={
                "user": current_user,
                "metrics": dashboard_data.get("metrics", {}),
                "my_jobs": dashboard_data.get("my_jobs", []),
            },
        )

    # System Admin, HR Recruiter, Admin, HR, Super Admin — all get the admin dashboard
    dashboard_data = await dashboard_service.get_admin_dashboard(current_user.id)
    return templates.TemplateResponse(
        request,
        "dashboard/index.html",
        context={
            "user": current_user,
            "metrics": dashboard_data.get("metrics", {}),
            "recent_logs": dashboard_data.get("recent_logs", []),
        },
    )