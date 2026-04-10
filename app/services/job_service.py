import logging
import math
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.job import Job
from app.models.user import User
from app.schemas.job import (
    JobCreate,
    JobFilterParams,
    JobUpdate,
)
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


ALLOWED_JOB_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "Draft": ["Published", "Closed"],
    "Published": ["Closed"],
    "Closed": [],
}


class JobService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job(self, data: JobCreate, user: User) -> Job:
        manager_result = await self.db.execute(
            select(User).where(User.id == data.hiring_manager_id, User.is_active == True)
        )
        manager = manager_result.scalars().first()
        if manager is None:
            raise ValueError(f"Hiring manager with ID {data.hiring_manager_id} not found or inactive.")

        job = Job(
            title=data.title,
            department=data.department,
            location=data.location,
            type=data.type,
            salary_min=data.salary_min,
            salary_max=data.salary_max,
            description=data.description,
            status="Draft",
            hiring_manager_id=data.hiring_manager_id,
        )

        self.db.add(job)
        await self.db.flush()
        await self.db.refresh(job)

        await audit_service.log_action(
            db=self.db,
            user_id=user.id,
            username=user.username,
            action="create_job",
            entity_type="Job",
            entity_id=job.id,
            details=f"Created job '{job.title}' in department '{job.department}'",
        )

        logger.info(
            "Job created: id=%d title='%s' by user_id=%d",
            job.id,
            job.title,
            user.id,
        )
        return job

    async def update_job(self, job_id: int, data: JobUpdate, user: User) -> Job:
        job = await self._get_job_or_raise(job_id)

        if data.hiring_manager_id is not None:
            manager_result = await self.db.execute(
                select(User).where(User.id == data.hiring_manager_id, User.is_active == True)
            )
            manager = manager_result.scalars().first()
            if manager is None:
                raise ValueError(f"Hiring manager with ID {data.hiring_manager_id} not found or inactive.")

        update_fields = data.model_dump(exclude_unset=True)
        if not update_fields:
            return job

        changes = []
        for field, value in update_fields.items():
            old_value = getattr(job, field, None)
            if old_value != value:
                setattr(job, field, value)
                changes.append(f"{field}: '{old_value}' -> '{value}'")

        if changes:
            await self.db.flush()
            await self.db.refresh(job)

            await audit_service.log_action(
                db=self.db,
                user_id=user.id,
                username=user.username,
                action="update_job",
                entity_type="Job",
                entity_id=job.id,
                details=f"Updated fields: {'; '.join(changes)}",
            )

            logger.info(
                "Job updated: id=%d by user_id=%d fields=%s",
                job.id,
                user.id,
                ", ".join(f.split(":")[0] for f in changes),
            )

        return job

    async def set_status(self, job_id: int, status: str, user: User) -> Job:
        job = await self._get_job_or_raise(job_id)

        allowed_statuses = {"Draft", "Published", "Closed"}
        if status not in allowed_statuses:
            raise ValueError(
                f"Invalid status '{status}'. Allowed values: {', '.join(sorted(allowed_statuses))}"
            )

        allowed_transitions = ALLOWED_JOB_STATUS_TRANSITIONS.get(job.status, [])
        if status not in allowed_transitions:
            raise ValueError(
                f"Invalid status transition from '{job.status}' to '{status}'. "
                f"Allowed transitions: {', '.join(allowed_transitions) if allowed_transitions else 'none'}"
            )

        old_status = job.status
        job.status = status

        await self.db.flush()
        await self.db.refresh(job)

        await audit_service.log_action(
            db=self.db,
            user_id=user.id,
            username=user.username,
            action="update_job_status",
            entity_type="Job",
            entity_id=job.id,
            details=f"Status changed from '{old_status}' to '{status}'",
        )

        logger.info(
            "Job status updated: id=%d '%s' -> '%s' by user_id=%d",
            job.id,
            old_status,
            status,
            user.id,
        )
        return job

    async def get_job_by_id(self, job_id: int) -> Optional[Job]:
        result = await self.db.execute(
            select(Job)
            .options(
                selectinload(Job.hiring_manager),
                selectinload(Job.applications),
            )
            .where(Job.id == job_id)
        )
        return result.scalars().first()

    async def list_jobs(
        self,
        filters: Optional[JobFilterParams] = None,
    ) -> dict[str, Any]:
        if filters is None:
            filters = JobFilterParams()

        query = select(Job).options(selectinload(Job.hiring_manager))
        count_query = select(func.count()).select_from(Job)

        if filters.status:
            query = query.where(Job.status == filters.status)
            count_query = count_query.where(Job.status == filters.status)

        if filters.department:
            query = query.where(Job.department == filters.department)
            count_query = count_query.where(Job.department == filters.department)

        if filters.location:
            query = query.where(Job.location == filters.location)
            count_query = count_query.where(Job.location == filters.location)

        if filters.job_type:
            query = query.where(Job.type == filters.job_type)
            count_query = count_query.where(Job.type == filters.job_type)

        if filters.search:
            search_term = f"%{filters.search}%"
            search_filter = or_(
                Job.title.ilike(search_term),
                Job.description.ilike(search_term),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        total_pages = max(1, math.ceil(total / filters.per_page))

        offset = (filters.page - 1) * filters.per_page
        query = query.order_by(Job.created_at.desc())
        query = query.offset(offset).limit(filters.per_page)

        result = await self.db.execute(query)
        jobs = list(result.scalars().all())

        return {
            "items": jobs,
            "total": total,
            "page": filters.page,
            "per_page": filters.per_page,
            "total_pages": total_pages,
        }

    async def get_published_jobs(self) -> list[Job]:
        result = await self.db.execute(
            select(Job)
            .options(selectinload(Job.hiring_manager))
            .where(Job.status == "Published")
            .order_by(Job.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_all_departments(self) -> list[str]:
        result = await self.db.execute(
            select(Job.department).distinct().order_by(Job.department)
        )
        departments = result.scalars().all()
        return [d for d in departments if d]

    async def get_hiring_managers(self) -> list[User]:
        result = await self.db.execute(
            select(User).where(User.is_active == True).order_by(User.username)
        )
        return list(result.scalars().all())

    async def _get_job_or_raise(self, job_id: int) -> Job:
        result = await self.db.execute(
            select(Job)
            .options(
                selectinload(Job.hiring_manager),
                selectinload(Job.applications),
            )
            .where(Job.id == job_id)
        )
        job = result.scalars().first()
        if job is None:
            raise ValueError(f"Job with ID {job_id} not found.")
        return job