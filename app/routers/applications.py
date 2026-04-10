import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user, require_login
from app.models.user import User
from app.services.application_service import ApplicationService
from app.services.candidate_service import CandidateService
from app.services.job_service import JobService

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/applications")
@router.get("/applications/")
async def list_applications(
    request: Request,
    status: Optional[str] = Query(None),
    job_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    application_service = ApplicationService(db)
    job_service = JobService(db)

    result = await application_service.list_applications(
        status=status,
        job_id=job_id,
        page=page,
        page_size=page_size,
    )

    jobs_result = await job_service.list_jobs()
    all_jobs = jobs_result.get("items", [])

    filters = {
        "status": status or "",
        "job_id": job_id or "",
    }

    return templates.TemplateResponse(
        request,
        "applications/list.html",
        context={
            "user": current_user,
            "applications": result["items"],
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
            "filters": filters,
            "jobs": all_jobs,
        },
    )


@router.get("/applications/pipeline")
async def application_pipeline(
    request: Request,
    job_id: Optional[int] = Query(None),
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    application_service = ApplicationService(db)

    job_filter = None
    if job_id is not None:
        job_service = JobService(db)
        job_filter = await job_service.get_job_by_id(job_id)

    result = await application_service.list_applications(
        job_id=job_id,
        page=1,
        page_size=500,
    )

    return templates.TemplateResponse(
        request,
        "applications/pipeline.html",
        context={
            "user": current_user,
            "applications": result["items"],
            "job_filter": job_filter,
        },
    )


@router.get("/applications/create")
async def create_application_form(
    request: Request,
    candidate_id: Optional[int] = Query(None),
    job_id: Optional[int] = Query(None),
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ["Admin", "HR", "System Admin", "HR Recruiter", "Super Admin"]:
        return RedirectResponse(url="/applications/", status_code=302)

    candidate_service = CandidateService(db)
    job_service = JobService(db)

    candidates_result = await candidate_service.list_candidates(page=1, page_size=500)
    jobs_result = await job_service.list_jobs()

    return templates.TemplateResponse(
        request,
        "applications/create.html",
        context={
            "user": current_user,
            "candidates": candidates_result["items"],
            "jobs": jobs_result["items"],
            "selected_candidate_id": candidate_id,
            "selected_job_id": job_id,
            "error": None,
        },
    )


@router.post("/applications/create")
async def create_application_submit(
    request: Request,
    candidate_id: int = Form(...),
    job_id: int = Form(...),
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ["Admin", "HR", "System Admin", "HR Recruiter", "Super Admin"]:
        return RedirectResponse(url="/applications/", status_code=302)

    application_service = ApplicationService(db)

    from app.schemas.application import ApplicationCreate

    try:
        data = ApplicationCreate(candidate_id=candidate_id, job_id=job_id)
        application = await application_service.create_application(data=data, user=current_user)
        logger.info(
            "Application %d created by user '%s'",
            application.id,
            current_user.username,
        )
        return RedirectResponse(
            url=f"/applications/{application.id}",
            status_code=302,
        )
    except ValueError as e:
        candidate_service = CandidateService(db)
        job_service = JobService(db)

        candidates_result = await candidate_service.list_candidates(page=1, page_size=500)
        jobs_result = await job_service.list_jobs()

        return templates.TemplateResponse(
            request,
            "applications/create.html",
            context={
                "user": current_user,
                "candidates": candidates_result["items"],
                "jobs": jobs_result["items"],
                "selected_candidate_id": candidate_id,
                "selected_job_id": job_id,
                "error": str(e),
            },
            status_code=400,
        )


@router.get("/applications/{application_id}")
async def application_detail(
    request: Request,
    application_id: int,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    application_service = ApplicationService(db)

    application = await application_service.get_application_by_id(application_id)
    if application is None:
        return templates.TemplateResponse(
            request,
            "applications/detail.html",
            context={
                "user": current_user,
                "application": None,
                "allowed_transitions": [],
                "interviews": [],
                "error": f"Application with id {application_id} not found.",
            },
            status_code=404,
        )

    allowed_transitions = await application_service.get_allowed_transitions(application_id)

    interviews = application.interviews if application.interviews else []

    return templates.TemplateResponse(
        request,
        "applications/detail.html",
        context={
            "user": current_user,
            "application": application,
            "allowed_transitions": allowed_transitions,
            "interviews": interviews,
        },
    )


@router.post("/applications/{application_id}/status")
async def update_application_status(
    request: Request,
    application_id: int,
    status: str = Form(...),
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in [
        "Admin",
        "HR",
        "System Admin",
        "HR Recruiter",
        "Super Admin",
        "Hiring Manager",
    ]:
        return RedirectResponse(
            url=f"/applications/{application_id}",
            status_code=302,
        )

    application_service = ApplicationService(db)

    try:
        application = await application_service.update_status(
            application_id=application_id,
            new_status=status,
            user=current_user,
        )
        logger.info(
            "Application %d status updated to '%s' by user '%s'",
            application.id,
            application.status,
            current_user.username,
        )
        return RedirectResponse(
            url=f"/applications/{application_id}",
            status_code=302,
        )
    except ValueError as e:
        application = await application_service.get_application_by_id(application_id)
        allowed_transitions = await application_service.get_allowed_transitions(application_id)
        interviews = application.interviews if application and application.interviews else []

        return templates.TemplateResponse(
            request,
            "applications/detail.html",
            context={
                "user": current_user,
                "application": application,
                "allowed_transitions": allowed_transitions,
                "interviews": interviews,
                "error": str(e),
            },
            status_code=400,
        )