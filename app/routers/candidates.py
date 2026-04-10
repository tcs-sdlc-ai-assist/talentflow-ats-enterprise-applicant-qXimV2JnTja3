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
from app.services.candidate_service import CandidateService

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/candidates")
@router.get("/candidates/")
async def candidates_list(
    request: Request,
    search: Optional[str] = Query(None),
    skill: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    candidate_service = CandidateService(db)

    skill_id = None
    if skill and skill.strip():
        try:
            skill_id = int(skill)
        except (ValueError, TypeError):
            skill_id = None

    result = await candidate_service.list_candidates(
        search=search if search and search.strip() else None,
        skill_id=skill_id,
        page=page,
        page_size=20,
    )

    all_skills = await candidate_service.get_all_skills()

    return templates.TemplateResponse(
        request,
        "candidates/list.html",
        context={
            "user": current_user,
            "candidates": result["items"],
            "total_count": result["total"],
            "page": result["page"],
            "total_pages": result.get("total_pages", 1),
            "search": search or "",
            "skill_filter": skill or "",
            "skills": all_skills,
        },
    )


@router.get("/candidates/create")
async def candidates_create_form(
    request: Request,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ["System Admin", "Admin", "HR Recruiter", "HR", "Super Admin"]:
        return RedirectResponse(url="/candidates/", status_code=302)

    return templates.TemplateResponse(
        request,
        "candidates/form.html",
        context={
            "user": current_user,
            "candidate": None,
            "error": None,
        },
    )


@router.post("/candidates/create")
async def candidates_create_submit(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    linkedin_url: str = Form(""),
    resume_text: str = Form(...),
    skills: str = Form(""),
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ["System Admin", "Admin", "HR Recruiter", "HR", "Super Admin"]:
        return RedirectResponse(url="/candidates/", status_code=302)

    candidate_service = CandidateService(db)

    name = f"{first_name.strip()} {last_name.strip()}".strip()

    skill_names = None
    if skills and skills.strip():
        skill_names = [s.strip() for s in skills.split(",") if s.strip()]

    try:
        candidate = await candidate_service.create_candidate(
            name=name,
            email=email,
            resume_text=resume_text,
            user=current_user,
            phone=phone if phone and phone.strip() else None,
            linkedin_url=linkedin_url if linkedin_url and linkedin_url.strip() else None,
            skill_names=skill_names,
        )
    except ValueError as e:
        return templates.TemplateResponse(
            request,
            "candidates/form.html",
            context={
                "user": current_user,
                "candidate": None,
                "error": str(e),
            },
            status_code=400,
        )

    logger.info(
        "Candidate created: id=%d name='%s' by user='%s'",
        candidate.id,
        candidate.name,
        current_user.username,
    )

    return RedirectResponse(url=f"/candidates/{candidate.id}", status_code=302)


@router.get("/candidates/{candidate_id}")
async def candidates_detail(
    request: Request,
    candidate_id: int,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    candidate_service = CandidateService(db)

    candidate = await candidate_service.get_candidate_by_id(candidate_id)
    if candidate is None:
        return templates.TemplateResponse(
            request,
            "candidates/list.html",
            context={
                "user": current_user,
                "candidates": [],
                "total_count": 0,
                "page": 1,
                "total_pages": 1,
                "search": "",
                "skill_filter": "",
                "skills": [],
                "error": f"Candidate with id {candidate_id} not found.",
            },
            status_code=404,
        )

    applications = candidate.applications if candidate.applications else []
    skills = candidate.skills if candidate.skills else []

    return templates.TemplateResponse(
        request,
        "candidates/detail.html",
        context={
            "user": current_user,
            "candidate": candidate,
            "applications": applications,
            "skills": skills,
        },
    )


@router.get("/candidates/{candidate_id}/edit")
async def candidates_edit_form(
    request: Request,
    candidate_id: int,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ["System Admin", "Admin", "HR Recruiter", "HR", "Super Admin"]:
        return RedirectResponse(url=f"/candidates/{candidate_id}", status_code=302)

    candidate_service = CandidateService(db)

    candidate = await candidate_service.get_candidate_by_id(candidate_id)
    if candidate is None:
        return RedirectResponse(url="/candidates/", status_code=302)

    return templates.TemplateResponse(
        request,
        "candidates/form.html",
        context={
            "user": current_user,
            "candidate": candidate,
            "error": None,
        },
    )


@router.post("/candidates/{candidate_id}/edit")
async def candidates_edit_submit(
    request: Request,
    candidate_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    linkedin_url: str = Form(""),
    resume_text: str = Form(...),
    skills: str = Form(""),
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ["System Admin", "Admin", "HR Recruiter", "HR", "Super Admin"]:
        return RedirectResponse(url=f"/candidates/{candidate_id}", status_code=302)

    candidate_service = CandidateService(db)

    existing_candidate = await candidate_service.get_candidate_by_id(candidate_id)
    if existing_candidate is None:
        return RedirectResponse(url="/candidates/", status_code=302)

    name = f"{first_name.strip()} {last_name.strip()}".strip()

    skill_names = None
    if skills is not None:
        if skills.strip():
            skill_names = [s.strip() for s in skills.split(",") if s.strip()]
        else:
            skill_names = []

    try:
        candidate = await candidate_service.update_candidate(
            candidate_id=candidate_id,
            user=current_user,
            name=name,
            email=email,
            resume_text=resume_text,
            phone=phone if phone and phone.strip() else "",
            linkedin_url=linkedin_url if linkedin_url and linkedin_url.strip() else "",
            skill_names=skill_names,
        )
    except ValueError as e:
        reload_candidate = await candidate_service.get_candidate_by_id(candidate_id)
        return templates.TemplateResponse(
            request,
            "candidates/form.html",
            context={
                "user": current_user,
                "candidate": reload_candidate if reload_candidate else existing_candidate,
                "error": str(e),
            },
            status_code=400,
        )

    logger.info(
        "Candidate updated: id=%d name='%s' by user='%s'",
        candidate.id,
        candidate.name,
        current_user.username,
    )

    return RedirectResponse(url=f"/candidates/{candidate.id}", status_code=302)