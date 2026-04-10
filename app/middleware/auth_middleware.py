from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_session_cookie
from app.models.user import User


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    cookie_value = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not cookie_value:
        return None

    session_data = decode_session_cookie(cookie_value)
    if session_data is None:
        return None

    user_id = session_data.get("user_id")
    if user_id is None:
        return None

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalars().first()
    return user


async def require_login(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
) -> User:
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
        )
    return current_user


def require_roles(allowed_roles: list[str]):
    async def _role_checker(
        current_user: User = Depends(require_login),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not authorized. Required role(s): {', '.join(allowed_roles)}. Your role: {current_user.role}.",
            )
        return current_user

    return _role_checker


require_admin = require_roles(["System Admin"])

require_hr_or_admin = require_roles(["System Admin", "HR Recruiter"])

require_manager_or_above = require_roles(["System Admin", "HR Recruiter", "Hiring Manager"])

require_any_authenticated = require_roles(["System Admin", "HR Recruiter", "Hiring Manager", "Interviewer"])