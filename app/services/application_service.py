import logging
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.user import User
from app.schemas.application import (
    ALLOWED_TRANSITIONS,
    APPLICATION_STATUSES,
    ApplicationCreate,
    ApplicationStatusUpdate,
)
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


class ApplicationService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_application(
        self,
        data: ApplicationCreate,
        user: User,
    ) -> Application:
        candidate_result = await self.db.execute(
            select(Candidate).where(Candidate.id == data.candidate_id)
        )
        candidate = candidate_result.scalars().first()
        if candidate is None:
            raise ValueError(f"Candidate with id {data.candidate_id} not found.")

        job_result = await self.db.execute(
            select(Job).where(Job.id == data.job_id)
        )
        job = job_result.scalars().first()
        if job is None:
            raise ValueError(f"Job with id {data.job_id} not found.")

        existing_result = await self.db.execute(
            select(Application).where(
                Application.candidate_id == data.candidate_id,
                Application.job_id == data.job_id,
            )
        )
        existing = existing_result.scalars().first()
        if existing is not None:
            raise ValueError(
                f"An application already exists for candidate {data.candidate_id} "
                f"and job {data.job_id}."
            )

        application = Application(
            candidate_id=data.candidate_id,
            job_id=data.job_id,
            status="Applied",
        )
        self.db.add(application)
        await self.db.flush()
        await self.db.refresh(application)

        await audit_service.log_action(
            db=self.db,
            user_id=user.id,
            username=user.username,
            action="create_application",
            entity_type="Application",
            entity_id=application.id,
            details=f"Created application for candidate {data.candidate_id} on job {data.job_id}",
        )

        logger.info(
            "Application %d created by user %s for candidate %d on job %d",
            application.id,
            user.username,
            data.candidate_id,
            data.job_id,
        )

        return application

    async def update_status(
        self,
        application_id: int,
        new_status: str,
        user: User,
    ) -> Application:
        if new_status not in APPLICATION_STATUSES:
            raise ValueError(
                f"Invalid status '{new_status}'. Must be one of: {', '.join(APPLICATION_STATUSES)}"
            )

        result = await self.db.execute(
            select(Application)
            .options(
                selectinload(Application.candidate),
                selectinload(Application.job),
            )
            .where(Application.id == application_id)
        )
        application = result.scalars().first()
        if application is None:
            raise ValueError(f"Application with id {application_id} not found.")

        current_status = application.status
        allowed = ALLOWED_TRANSITIONS.get(current_status, [])

        if new_status not in allowed:
            raise ValueError(
                f"Invalid status transition from '{current_status}' to '{new_status}'. "
                f"Allowed transitions from '{current_status}': {', '.join(allowed) if allowed else 'none'}"
            )

        old_status = application.status
        application.status = new_status
        await self.db.flush()
        await self.db.refresh(application)

        await audit_service.log_action(
            db=self.db,
            user_id=user.id,
            username=user.username,
            action="application_status_update",
            entity_type="Application",
            entity_id=application.id,
            details=f"Status changed from '{old_status}' to '{new_status}'",
        )

        logger.info(
            "Application %d status updated from '%s' to '%s' by user %s",
            application.id,
            old_status,
            new_status,
            user.username,
        )

        return application

    async def get_application_by_id(
        self,
        application_id: int,
    ) -> Optional[Application]:
        result = await self.db.execute(
            select(Application)
            .options(
                selectinload(Application.candidate),
                selectinload(Application.job),
                selectinload(Application.interviews),
            )
            .where(Application.id == application_id)
        )
        return result.scalars().first()

    async def list_applications(
        self,
        status: Optional[str] = None,
        job_id: Optional[int] = None,
        candidate_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        query = select(Application).options(
            selectinload(Application.candidate),
            selectinload(Application.job),
        )
        count_query = select(func.count()).select_from(Application)

        if status is not None and status != "":
            query = query.where(Application.status == status)
            count_query = count_query.where(Application.status == status)

        if job_id is not None:
            query = query.where(Application.job_id == job_id)
            count_query = count_query.where(Application.job_id == job_id)

        if candidate_id is not None:
            query = query.where(Application.candidate_id == candidate_id)
            count_query = count_query.where(Application.candidate_id == candidate_id)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(Application.created_at.desc())
        query = query.offset(offset).limit(page_size)

        result = await self.db.execute(query)
        applications = list(result.scalars().all())

        return {
            "items": applications,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_applications_for_job(
        self,
        job_id: int,
    ) -> list[Application]:
        result = await self.db.execute(
            select(Application)
            .options(
                selectinload(Application.candidate),
                selectinload(Application.job),
            )
            .where(Application.job_id == job_id)
            .order_by(Application.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_applications_for_candidate(
        self,
        candidate_id: int,
    ) -> list[Application]:
        result = await self.db.execute(
            select(Application)
            .options(
                selectinload(Application.candidate),
                selectinload(Application.job),
            )
            .where(Application.candidate_id == candidate_id)
            .order_by(Application.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_allowed_transitions(self, application_id: int) -> list[str]:
        result = await self.db.execute(
            select(Application).where(Application.id == application_id)
        )
        application = result.scalars().first()
        if application is None:
            return []
        return ALLOWED_TRANSITIONS.get(application.status, [])