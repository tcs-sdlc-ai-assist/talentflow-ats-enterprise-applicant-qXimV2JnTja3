import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_session_cookie,
    decode_session_cookie,
    get_password_hash,
    verify_password,
)
from app.models.user import User

logger = logging.getLogger(__name__)


class AuthService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def login(self, username: str, password: str) -> Optional[User]:
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            logger.warning("Login failed: user '%s' not found", username)
            return None

        if not user.is_active:
            logger.warning("Login failed: user '%s' is inactive", username)
            return None

        if not verify_password(password, user.hashed_password):
            logger.warning("Login failed: invalid password for user '%s'", username)
            return None

        logger.info("User '%s' logged in successfully", username)
        return user

    async def register(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        role: str = "Interviewer",
    ) -> User:
        existing_stmt = select(User).where(User.username == username)
        result = await self.db.execute(existing_stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user is not None:
            raise ValueError("Username already exists.")

        if email:
            email_stmt = select(User).where(User.email == email)
            email_result = await self.db.execute(email_stmt)
            existing_email = email_result.scalar_one_or_none()
            if existing_email is not None:
                raise ValueError("Email already exists.")

        hashed_password = get_password_hash(password)

        user = User(
            username=username,
            hashed_password=hashed_password,
            email=email,
            full_name=full_name,
            role=role,
            is_active=True,
        )

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        logger.info("User '%s' registered with role '%s'", username, role)
        return user

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Optional[User]:
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def create_session(self, user: User) -> str:
        return create_session_cookie(
            user_id=user.id,
            username=user.username,
            role=user.role,
        )

    @staticmethod
    def decode_session(cookie_value: str) -> Optional[dict]:
        return decode_session_cookie(cookie_value)

    @staticmethod
    def get_session_cookie_name() -> str:
        return settings.SESSION_COOKIE_NAME

    @staticmethod
    def get_session_max_age() -> int:
        return settings.SESSION_MAX_AGE


async def seed_default_admin(db: AsyncSession) -> None:
    admin_username = settings.DEFAULT_ADMIN_USERNAME
    admin_password = settings.DEFAULT_ADMIN_PASSWORD

    stmt = select(User).where(User.username == admin_username)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is not None:
        logger.info("Default admin user '%s' already exists, skipping seed", admin_username)
        return

    hashed_password = get_password_hash(admin_password)

    admin_user = User(
        username=admin_username,
        hashed_password=hashed_password,
        role="Admin",
        is_active=True,
    )

    db.add(admin_user)
    await db.commit()
    logger.info("Default admin user '%s' created successfully", admin_username)