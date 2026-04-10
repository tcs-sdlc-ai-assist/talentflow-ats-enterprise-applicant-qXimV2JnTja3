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
from app.schemas.job import JobCreate, JobFilterParams, JobUpdate
from app.services.job_service import JobService
from app.services.application_service import ApplicationService

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/jobs")
@router.get("/jobs/")
async def list_jobs(
    request: Request,
    search: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    job_service = JobService(db)

    filters = JobFilterParams(
        search=search,
        department=department,
        status=status,
        page=page,
        per_page=per_page,
    )

    result = await job_service.list_jobs(filters=filters)

    departments = await job_service.get_all_departments()

    return templates.TemplateResponse(
        request,
        "jobs/list.html",
        context={
            "user": current_user,
            "jobs": result["items"],
            "filters": {
                "search": search or "",
                "department": department or "",
                "status": status or "",
            },
            "departments": departments,
            "page": result["page"],
            "total_pages": result["total_pages"],
            "total_count": result["total"],
        },
    )


@router.get("/jobs/create")
async def create_job_form(
    request: Request,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ["Admin", "System Admin", "HR Recruiter", "HR", "Super Admin"]:
        return RedirectResponse(url="/jobs/", status_code=302)

    job_service = JobService(db)
    hiring_managers = await job_service.get_hiring_managers()

    return templates.TemplateResponse(
        request,
        "jobs/form.html",
        context={
            "user": current_user,
            "job": None,
            "hiring_managers": hiring_managers,
            "error": None,
        },
    )


@router.post("/jobs")
@router.post("/jobs/")
async def create_job_submit(
    request: Request,
    title: str = Form(...),
    department: str = Form(...),
    location: str = Form(...),
    type: str = Form(...),
    salary_min: int = Form(...),
    salary_max: int = Form(...),
    description: str = Form(...),
    hiring_manager_id: int = Form(...),
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ["Admin", "System Admin", "HR Recruiter", "HR", "Super Admin"]:
        return RedirectResponse(url="/jobs/", status_code=302)

    job_service = JobService(db)

    try:
        data = JobCreate(
            title=title,
            department=department,
            location=location,
            type=type,
            salary_min=salary_min,
            salary_max=salary_max,
            description=description,
            hiring_manager_id=hiring_manager_id,
        )
    except Exception as e:
        hiring_managers = await job_service.get_hiring_managers()
        return templates.TemplateResponse(
            request,
            "jobs/form.html",
            context={
                "user": current_user,
                "job": None,
                "hiring_managers": hiring_managers,
                "error": str(e),
            },
            status_code=400,
        )

    try:
        job = await job_service.create_job(data=data, user=current_user)
    except ValueError as e:
        hiring_managers = await job_service.get_hiring_managers()
        return templates.TemplateResponse(
            request,
            "jobs/form.html",
            context={
                "user": current_user,
                "job": None,
                "hiring_managers": hiring_managers,
                "error": str(e),
            },
            status_code=400,
        )

    logger.info("Job %d created by user %s", job.id, current_user.username)
    return RedirectResponse(url=f"/jobs/{job.id}", status_code=302)


@router.get("/jobs/{job_id}")
async def job_detail(
    request: Request,
    job_id: int,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    job_service = JobService(db)
    application_service = ApplicationService(db)

    job = await job_service.get_job_by_id(job_id)
    if job is None:
        return RedirectResponse(url="/jobs/", status_code=302)

    applications = await application_service.get_applications_for_job(job_id)

    hiring_manager = job.hiring_manager if job.hiring_manager else None

    return templates.TemplateResponse(
        request,
        "jobs/detail.html",
        context={
            "user": current_user,
            "job": job,
            "hiring_manager": hiring_manager,
            "applications": applications,
        },
    )


@router.get("/jobs/{job_id}/edit")
async def edit_job_form(
    request: Request,
    job_id: int,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    job_service = JobService(db)

    job = await job_service.get_job_by_id(job_id)
    if job is None:
        return RedirectResponse(url="/jobs/", status_code=302)

    is_admin_or_hr = current_user.role in [
        "Admin", "System Admin", "HR Recruiter", "HR", "Super Admin",
    ]
    is_hiring_manager = (
        current_user.role == "Hiring Manager"
        and job.hiring_manager_id == current_user.id
    )

    if not is_admin_or_hr and not is_hiring_manager:
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)

    hiring_managers = await job_service.get_hiring_managers()

    return templates.TemplateResponse(
        request,
        "jobs/form.html",
        context={
            "user": current_user,
            "job": job,
            "hiring_managers": hiring_managers,
            "error": None,
        },
    )


@router.post("/jobs/{job_id}")
async def update_job_submit(
    request: Request,
    job_id: int,
    title: str = Form(...),
    department: str = Form(...),
    location: str = Form(...),
    type: str = Form(...),
    salary_min: int = Form(...),
    salary_max: int = Form(...),
    description: str = Form(...),
    hiring_manager_id: int = Form(...),
    status: Optional[str] = Form(None),
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    job_service = JobService(db)

    job = await job_service.get_job_by_id(job_id)
    if job is None:
        return RedirectResponse(url="/jobs/", status_code=302)

    is_admin_or_hr = current_user.role in [
        "Admin", "System Admin", "HR Recruiter", "HR", "Super Admin",
    ]
    is_hiring_manager = (
        current_user.role == "Hiring Manager"
        and job.hiring_manager_id == current_user.id
    )

    if not is_admin_or_hr and not is_hiring_manager:
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)

    try:
        data = JobUpdate(
            title=title,
            department=department,
            location=location,
            type=type,
            salary_min=salary_min,
            salary_max=salary_max,
            description=description,
            hiring_manager_id=hiring_manager_id,
        )
    except Exception as e:
        hiring_managers = await job_service.get_hiring_managers()
        return templates.TemplateResponse(
            request,
            "jobs/form.html",
            context={
                "user": current_user,
                "job": job,
                "hiring_managers": hiring_managers,
                "error": str(e),
            },
            status_code=400,
        )

    try:
        updated_job = await job_service.update_job(job_id=job_id, data=data, user=current_user)
    except ValueError as e:
        hiring_managers = await job_service.get_hiring_managers()
        return templates.TemplateResponse(
            request,
            "jobs/form.html",
            context={
                "user": current_user,
                "job": job,
                "hiring_managers": hiring_managers,
                "error": str(e),
            },
            status_code=400,
        )

    if status and status != job.status:
        try:
            await job_service.set_status(job_id=job_id, status=status, user=current_user)
        except ValueError as e:
            hiring_managers = await job_service.get_hiring_managers()
            return templates.TemplateResponse(
                request,
                "jobs/form.html",
                context={
                    "user": current_user,
                    "job": updated_job,
                    "hiring_managers": hiring_managers,
                    "error": str(e),
                },
                status_code=400,
            )

    logger.info("Job %d updated by user %s", job_id, current_user.username)
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)


@router.post("/jobs/{job_id}/status")
async def update_job_status(
    request: Request,
    job_id: int,
    status: str = Form(...),
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    job_service = JobService(db)

    job = await job_service.get_job_by_id(job_id)
    if job is None:
        return RedirectResponse(url="/jobs/", status_code=302)

    is_admin_or_hr = current_user.role in [
        "Admin", "System Admin", "HR Recruiter", "HR", "Super Admin",
    ]
    is_hiring_manager = (
        current_user.role == "Hiring Manager"
        and job.hiring_manager_id == current_user.id
    )

    if not is_admin_or_hr and not is_hiring_manager:
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)

    try:
        await job_service.set_status(job_id=job_id, status=status, user=current_user)
    except ValueError as e:
        logger.warning(
            "Failed to update job %d status to '%s': %s",
            job_id,
            status,
            str(e),
        )
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)

    logger.info(
        "Job %d status updated to '%s' by user %s",
        job_id,
        status,
        current_user.username,
    )
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)