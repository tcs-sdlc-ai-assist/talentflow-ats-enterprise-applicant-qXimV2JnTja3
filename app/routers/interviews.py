import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user, require_login
from app.models.user import User
from app.services.interview_service import InterviewService
from app.services.application_service import ApplicationService
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/interviews/")
@router.get("/interviews")
async def list_interviews(
    request: Request,
    feedback_status: Optional[str] = None,
    application_id: Optional[int] = None,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    interview_service = InterviewService(db)

    interviews = await interview_service.list_interviews(
        feedback_status=feedback_status,
        application_id=application_id,
    )

    filters = {
        "feedback_status": feedback_status or "",
    }

    return templates.TemplateResponse(
        request,
        "interviews/list.html",
        context={
            "user": current_user,
            "interviews": interviews,
            "filters": filters,
        },
    )


@router.get("/interviews/my")
async def my_interviews(
    request: Request,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    interview_service = InterviewService(db)

    interviews = await interview_service.get_interviews_for_user(current_user.id)

    return templates.TemplateResponse(
        request,
        "interviews/my.html",
        context={
            "user": current_user,
            "interviews": interviews,
        },
    )


@router.get("/interviews/schedule")
async def schedule_interview_form(
    request: Request,
    application_id: Optional[int] = None,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ["System Admin", "Admin", "HR Recruiter", "HR", "Super Admin"]:
        return RedirectResponse(url="/interviews/", status_code=302)

    application_service = ApplicationService(db)
    applications_data = await application_service.list_applications(page=1, page_size=500)
    applications = applications_data.get("items", [])

    from sqlalchemy import select
    from app.models.user import User as UserModel

    result = await db.execute(
        select(UserModel).where(UserModel.is_active == True).order_by(UserModel.username)
    )
    interviewers = list(result.scalars().all())

    return templates.TemplateResponse(
        request,
        "interviews/schedule_form.html",
        context={
            "user": current_user,
            "applications": applications,
            "interviewers": interviewers,
            "selected_application_id": application_id,
            "error": None,
        },
    )


@router.post("/interviews/schedule")
async def schedule_interview_submit(
    request: Request,
    application_id: int = Form(...),
    interviewer_id: int = Form(...),
    scheduled_at: str = Form(...),
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ["System Admin", "Admin", "HR Recruiter", "HR", "Super Admin"]:
        return RedirectResponse(url="/interviews/", status_code=302)

    from datetime import datetime

    try:
        scheduled_datetime = datetime.fromisoformat(scheduled_at)
    except (ValueError, TypeError):
        application_service = ApplicationService(db)
        applications_data = await application_service.list_applications(page=1, page_size=500)
        applications = applications_data.get("items", [])

        from sqlalchemy import select
        from app.models.user import User as UserModel

        result = await db.execute(
            select(UserModel).where(UserModel.is_active == True).order_by(UserModel.username)
        )
        interviewers = list(result.scalars().all())

        return templates.TemplateResponse(
            request,
            "interviews/schedule_form.html",
            context={
                "user": current_user,
                "applications": applications,
                "interviewers": interviewers,
                "selected_application_id": application_id,
                "error": "Invalid date/time format. Please use a valid date and time.",
            },
            status_code=400,
        )

    interview_service = InterviewService(db)

    try:
        interview = await interview_service.schedule_interview(
            application_id=application_id,
            interviewer_id=interviewer_id,
            scheduled_at=scheduled_datetime,
            user=current_user,
        )
    except ValueError as e:
        application_service = ApplicationService(db)
        applications_data = await application_service.list_applications(page=1, page_size=500)
        applications = applications_data.get("items", [])

        from sqlalchemy import select
        from app.models.user import User as UserModel

        result = await db.execute(
            select(UserModel).where(UserModel.is_active == True).order_by(UserModel.username)
        )
        interviewers = list(result.scalars().all())

        return templates.TemplateResponse(
            request,
            "interviews/schedule_form.html",
            context={
                "user": current_user,
                "applications": applications,
                "interviewers": interviewers,
                "selected_application_id": application_id,
                "error": str(e),
            },
            status_code=400,
        )

    logger.info(
        "Interview #%d scheduled by user '%s'",
        interview.id,
        current_user.username,
    )

    return RedirectResponse(url="/interviews/", status_code=302)


@router.get("/interviews/{interview_id}")
async def interview_detail(
    request: Request,
    interview_id: int,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    interview_service = InterviewService(db)

    interview = await interview_service.get_interview_by_id(interview_id)

    if interview is None:
        return templates.TemplateResponse(
            request,
            "interviews/feedback_form.html",
            context={
                "user": current_user,
                "interview": None,
                "error": f"Interview with id {interview_id} not found.",
            },
            status_code=404,
        )

    return templates.TemplateResponse(
        request,
        "interviews/feedback_form.html",
        context={
            "user": current_user,
            "interview": interview,
            "error": None,
        },
    )


@router.get("/interviews/{interview_id}/feedback")
async def feedback_form(
    request: Request,
    interview_id: int,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    interview_service = InterviewService(db)

    interview = await interview_service.get_interview_by_id(interview_id)

    if interview is None:
        return templates.TemplateResponse(
            request,
            "interviews/feedback_form.html",
            context={
                "user": current_user,
                "interview": None,
                "error": f"Interview with id {interview_id} not found.",
            },
            status_code=404,
        )

    is_admin = current_user.role in ["System Admin", "Admin", "HR Recruiter", "HR", "Super Admin"]
    is_interviewer = interview.interviewer_id == current_user.id

    if not is_admin and not is_interviewer:
        return RedirectResponse(url="/interviews/my", status_code=302)

    return templates.TemplateResponse(
        request,
        "interviews/feedback_form.html",
        context={
            "user": current_user,
            "interview": interview,
            "error": None,
        },
    )


@router.post("/interviews/{interview_id}/feedback")
async def submit_feedback(
    request: Request,
    interview_id: int,
    feedback_rating: int = Form(...),
    feedback_notes: str = Form(""),
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    interview_service = InterviewService(db)

    interview = await interview_service.get_interview_by_id(interview_id)

    if interview is None:
        return templates.TemplateResponse(
            request,
            "interviews/feedback_form.html",
            context={
                "user": current_user,
                "interview": None,
                "error": f"Interview with id {interview_id} not found.",
            },
            status_code=404,
        )

    is_admin = current_user.role in ["System Admin", "Admin", "HR Recruiter", "HR", "Super Admin"]
    is_interviewer = interview.interviewer_id == current_user.id

    if not is_admin and not is_interviewer:
        return RedirectResponse(url="/interviews/my", status_code=302)

    try:
        interview = await interview_service.submit_feedback(
            interview_id=interview_id,
            rating=feedback_rating,
            notes=feedback_notes,
            user=current_user,
        )
    except ValueError as e:
        interview = await interview_service.get_interview_by_id(interview_id)

        return templates.TemplateResponse(
            request,
            "interviews/feedback_form.html",
            context={
                "user": current_user,
                "interview": interview,
                "error": str(e),
            },
            status_code=400,
        )

    logger.info(
        "Feedback submitted for interview #%d by user '%s'",
        interview_id,
        current_user.username,
    )

    if is_interviewer and not is_admin:
        return RedirectResponse(url="/interviews/my", status_code=302)

    return RedirectResponse(url=f"/interviews/{interview_id}/feedback", status_code=302)