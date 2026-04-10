import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/login")
async def login_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        context={"user": None, "error": None, "username": ""},
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(db)

    user = await auth_service.login(username, password)

    if user is None:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            context={
                "user": None,
                "error": "Invalid username or password.",
                "username": username,
            },
            status_code=401,
        )

    session_cookie = auth_service.create_session(user)

    redirect_url = _get_role_redirect(user.role)

    response = RedirectResponse(url=redirect_url, status_code=302)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_cookie,
        max_age=settings.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )

    try:
        await audit_service.log_action(
            db=db,
            user_id=user.id,
            username=user.username,
            action="login",
            entity_type="User",
            entity_id=user.id,
            details=f"User '{user.username}' logged in",
        )
    except Exception:
        logger.warning("Failed to log audit entry for login of user '%s'", user.username)

    logger.info("User '%s' logged in, redirecting to %s", user.username, redirect_url)
    return response


@router.get("/register")
async def register_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(
        request,
        "auth/register.html",
        context={
            "user": None,
            "error": None,
            "errors": [],
            "form_data": None,
        },
    )


@router.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    email: str = Form(""),
    full_name: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    errors: list[str] = []
    form_data = {
        "username": username,
        "email": email,
        "full_name": full_name,
    }

    username = username.strip()
    email = email.strip() if email else ""
    full_name = full_name.strip() if full_name else ""

    if not username:
        errors.append("Username is required.")
    elif len(username) < 3 or len(username) > 32:
        errors.append("Username must be between 3 and 32 characters.")
    else:
        import re
        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            errors.append("Username must contain only alphanumeric characters and underscores.")

    if not password:
        errors.append("Password is required.")
    elif len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    else:
        import re
        if not re.search(r"[a-zA-Z]", password):
            errors.append("Password must contain at least one letter.")
        if not re.search(r"[0-9]", password):
            errors.append("Password must contain at least one number.")

    if password != confirm_password:
        errors.append("Passwords do not match.")

    if errors:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "user": None,
                "error": None,
                "errors": errors,
                "form_data": form_data,
            },
            status_code=400,
        )

    auth_service = AuthService(db)

    try:
        user = await auth_service.register(
            username=username,
            password=password,
            email=email if email else None,
            full_name=full_name if full_name else None,
            role="Interviewer",
        )
    except ValueError as e:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "user": None,
                "error": str(e),
                "errors": [],
                "form_data": form_data,
            },
            status_code=400,
        )

    session_cookie = auth_service.create_session(user)

    redirect_url = _get_role_redirect(user.role)

    response = RedirectResponse(url=redirect_url, status_code=302)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_cookie,
        max_age=settings.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )

    try:
        await audit_service.log_action(
            db=db,
            user_id=user.id,
            username=user.username,
            action="register",
            entity_type="User",
            entity_id=user.id,
            details=f"User '{user.username}' registered with role 'Interviewer'",
        )
    except Exception:
        logger.warning("Failed to log audit entry for registration of user '%s'", user.username)

    logger.info("User '%s' registered and logged in", user.username)
    return response


@router.post("/auth/logout")
async def logout(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user is not None:
        try:
            await audit_service.log_action(
                db=db,
                user_id=current_user.id,
                username=current_user.username,
                action="logout",
                entity_type="User",
                entity_id=current_user.id,
                details=f"User '{current_user.username}' logged out",
            )
        except Exception:
            logger.warning(
                "Failed to log audit entry for logout of user '%s'",
                current_user.username,
            )

    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
    )

    logger.info(
        "User '%s' logged out",
        current_user.username if current_user else "unknown",
    )
    return response


def _get_role_redirect(role: str) -> str:
    role_redirects = {
        "System Admin": "/dashboard",
        "Admin": "/dashboard",
        "HR Recruiter": "/dashboard",
        "HR": "/dashboard",
        "Super Admin": "/dashboard",
        "Hiring Manager": "/dashboard",
        "Interviewer": "/interviews/my",
    }
    return role_redirects.get(role, "/dashboard")