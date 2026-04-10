from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.audit_log import AuditLog
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.job import Job
from app.models.user import User


class MetricsAggregator:
    """Aggregates recruitment metrics from the database."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_open_jobs_count(self) -> int:
        result = await self.db.execute(
            select(func.count(Job.id)).where(Job.status == "Published")
        )
        return result.scalar_one_or_none() or 0

    async def get_total_candidates_count(self) -> int:
        result = await self.db.execute(
            select(func.count(Candidate.id))
        )
        return result.scalar_one_or_none() or 0

    async def get_active_applications_count(self) -> int:
        result = await self.db.execute(
            select(func.count(Application.id)).where(
                Application.status.notin_(["Hired", "Rejected"])
            )
        )
        return result.scalar_one_or_none() or 0

    async def get_scheduled_interviews_count(self) -> int:
        now = datetime.utcnow()
        result = await self.db.execute(
            select(func.count(Interview.id)).where(
                Interview.scheduled_at >= now,
                Interview.feedback_submitted_at.is_(None),
            )
        )
        return result.scalar_one_or_none() or 0

    async def get_jobs_by_hiring_manager(self, user_id: int) -> int:
        result = await self.db.execute(
            select(func.count(Job.id)).where(Job.hiring_manager_id == user_id)
        )
        return result.scalar_one_or_none() or 0

    async def get_pending_interviews_for_manager(self, user_id: int) -> int:
        result = await self.db.execute(
            select(func.count(Interview.id))
            .join(Application, Interview.application_id == Application.id)
            .join(Job, Application.job_id == Job.id)
            .where(
                Job.hiring_manager_id == user_id,
                Interview.feedback_submitted_at.is_(None),
            )
        )
        return result.scalar_one_or_none() or 0

    async def get_upcoming_interviews_for_interviewer(self, user_id: int) -> int:
        now = datetime.utcnow()
        result = await self.db.execute(
            select(func.count(Interview.id)).where(
                Interview.interviewer_id == user_id,
                Interview.scheduled_at >= now,
            )
        )
        return result.scalar_one_or_none() or 0

    async def get_missing_feedback_count(self, user_id: int) -> int:
        now = datetime.utcnow()
        result = await self.db.execute(
            select(func.count(Interview.id)).where(
                Interview.interviewer_id == user_id,
                Interview.scheduled_at < now,
                Interview.feedback_submitted_at.is_(None),
            )
        )
        return result.scalar_one_or_none() or 0


class DashboardService:
    """Provides role-specific dashboard data."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.metrics = MetricsAggregator(db)

    async def get_admin_dashboard(self, user_id: int) -> dict[str, Any]:
        metrics = {
            "open_jobs": await self.metrics.get_open_jobs_count(),
            "total_candidates": await self.metrics.get_total_candidates_count(),
            "active_applications": await self.metrics.get_active_applications_count(),
            "scheduled_interviews": await self.metrics.get_scheduled_interviews_count(),
        }
        recent_logs = await self._get_recent_audit_logs(limit=10)
        return {
            "metrics": metrics,
            "recent_logs": recent_logs,
        }

    async def get_hiring_manager_dashboard(self, user_id: int) -> dict[str, Any]:
        my_jobs_count = await self.metrics.get_jobs_by_hiring_manager(user_id)
        pending_interviews = await self.metrics.get_pending_interviews_for_manager(user_id)

        metrics = {
            "my_jobs": my_jobs_count,
            "pending_interviews": pending_interviews,
        }

        my_jobs = await self._get_jobs_for_hiring_manager(user_id)

        return {
            "metrics": metrics,
            "my_jobs": my_jobs,
        }

    async def get_interviewer_dashboard(self, user_id: int) -> dict[str, Any]:
        upcoming_count = await self.metrics.get_upcoming_interviews_for_interviewer(user_id)
        missing_feedback = await self.metrics.get_missing_feedback_count(user_id)

        metrics = {
            "upcoming_interviews": upcoming_count,
            "missing_feedback": missing_feedback,
        }

        upcoming_interviews = await self._get_upcoming_interviews_for_user(user_id)

        return {
            "metrics": metrics,
            "upcoming_interviews": upcoming_interviews,
        }

    async def get_dashboard_data(self, user_id: int, role: str) -> dict[str, Any]:
        if role in ("System Admin", "HR Recruiter", "Admin", "HR", "Super Admin"):
            return await self.get_admin_dashboard(user_id)
        elif role == "Hiring Manager":
            return await self.get_hiring_manager_dashboard(user_id)
        elif role == "Interviewer":
            return await self.get_interviewer_dashboard(user_id)
        else:
            return {
                "metrics": {},
                "recent_logs": [],
            }

    async def _get_recent_audit_logs(self, limit: int = 10) -> list[AuditLog]:
        result = await self.db.execute(
            select(AuditLog)
            .options(selectinload(AuditLog.user))
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _get_jobs_for_hiring_manager(self, user_id: int) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(Job)
            .options(selectinload(Job.applications))
            .where(Job.hiring_manager_id == user_id)
            .order_by(Job.created_at.desc())
            .limit(10)
        )
        jobs = result.scalars().all()

        job_list = []
        for job in jobs:
            job_list.append({
                "id": job.id,
                "title": job.title,
                "department": job.department,
                "status": job.status,
                "created_at": job.created_at,
                "application_count": len(job.applications) if job.applications else 0,
            })
        return job_list

    async def _get_upcoming_interviews_for_user(self, user_id: int) -> list[dict[str, Any]]:
        now = datetime.utcnow()
        result = await self.db.execute(
            select(Interview)
            .options(
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job),
            )
            .where(
                Interview.interviewer_id == user_id,
                Interview.scheduled_at >= now,
            )
            .order_by(Interview.scheduled_at.asc())
            .limit(10)
        )
        interviews = result.scalars().all()

        interview_list = []
        for interview in interviews:
            candidate_name = "Unknown"
            job_title = "Unknown"
            status = "Scheduled"

            if interview.application:
                if interview.application.candidate:
                    candidate_name = interview.application.candidate.name
                if interview.application.job:
                    job_title = interview.application.job.title

            if interview.feedback_submitted_at:
                status = "Completed"

            interview_list.append({
                "id": interview.id,
                "candidate_name": candidate_name,
                "job_title": job_title,
                "scheduled_at": interview.scheduled_at,
                "status": status,
                "feedback_rating": interview.feedback_rating,
            })
        return interview_list