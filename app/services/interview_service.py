import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.interview import Interview
from app.models.user import User
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


class InterviewService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def schedule_interview(
        self,
        application_id: int,
        interviewer_id: int,
        scheduled_at: datetime,
        user: User,
    ) -> Interview:
        result = await self.db.execute(
            select(Application).where(Application.id == application_id)
        )
        application = result.scalars().first()
        if application is None:
            raise ValueError(f"Application with id {application_id} not found")

        result = await self.db.execute(
            select(User).where(User.id == interviewer_id, User.is_active == True)
        )
        interviewer = result.scalars().first()
        if interviewer is None:
            raise ValueError(f"Interviewer with id {interviewer_id} not found")

        interview = Interview(
            application_id=application_id,
            interviewer_id=interviewer_id,
            scheduled_at=scheduled_at,
        )
        self.db.add(interview)
        await self.db.flush()
        await self.db.refresh(interview)

        await audit_service.log_action(
            db=self.db,
            user_id=user.id,
            username=user.username,
            action="schedule_interview",
            entity_type="Interview",
            entity_id=interview.id,
            details=f"Scheduled interview for application #{application_id} with interviewer #{interviewer_id} at {scheduled_at.isoformat()}",
        )

        logger.info(
            "Interview #%d scheduled: application_id=%d, interviewer_id=%d, scheduled_at=%s",
            interview.id,
            application_id,
            interviewer_id,
            scheduled_at.isoformat(),
        )

        return interview

    async def submit_feedback(
        self,
        interview_id: int,
        rating: int,
        notes: str,
        user: User,
    ) -> Interview:
        if rating < 1 or rating > 5:
            raise ValueError("Feedback rating must be between 1 and 5")

        if not notes or not notes.strip():
            raise ValueError("Feedback notes must not be empty")

        result = await self.db.execute(
            select(Interview)
            .options(
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job),
                selectinload(Interview.interviewer),
            )
            .where(Interview.id == interview_id)
        )
        interview = result.scalars().first()
        if interview is None:
            raise ValueError(f"Interview with id {interview_id} not found")

        if interview.feedback_submitted_at is not None:
            raise ValueError("Feedback has already been submitted for this interview")

        interview.feedback_rating = rating
        interview.feedback_notes = notes.strip()
        interview.feedback_submitted_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(interview)

        await audit_service.log_action(
            db=self.db,
            user_id=user.id,
            username=user.username,
            action="submit_feedback",
            entity_type="Interview",
            entity_id=interview.id,
            details=f"Submitted feedback for interview #{interview_id}: rating={rating}",
        )

        logger.info(
            "Feedback submitted for interview #%d by user '%s': rating=%d",
            interview_id,
            user.username,
            rating,
        )

        return interview

    async def list_interviews(
        self,
        feedback_status: Optional[str] = None,
        application_id: Optional[int] = None,
    ) -> list[Interview]:
        query = (
            select(Interview)
            .options(
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job),
                selectinload(Interview.interviewer),
            )
        )

        if feedback_status == "pending":
            query = query.where(Interview.feedback_submitted_at.is_(None))
        elif feedback_status == "submitted":
            query = query.where(Interview.feedback_submitted_at.isnot(None))

        if application_id is not None:
            query = query.where(Interview.application_id == application_id)

        query = query.order_by(Interview.scheduled_at.desc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_interview_by_id(self, interview_id: int) -> Optional[Interview]:
        result = await self.db.execute(
            select(Interview)
            .options(
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job),
                selectinload(Interview.interviewer),
            )
            .where(Interview.id == interview_id)
        )
        return result.scalars().first()

    async def get_interviews_for_user(self, user_id: int) -> list[Interview]:
        query = (
            select(Interview)
            .options(
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job),
                selectinload(Interview.interviewer),
            )
            .where(Interview.interviewer_id == user_id)
            .order_by(Interview.scheduled_at.asc())
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_interviews_for_application(self, application_id: int) -> list[Interview]:
        query = (
            select(Interview)
            .options(
                selectinload(Interview.interviewer),
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job),
            )
            .where(Interview.application_id == application_id)
            .order_by(Interview.scheduled_at.asc())
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_interview_count(
        self,
        feedback_status: Optional[str] = None,
    ) -> int:
        query = select(func.count(Interview.id))

        if feedback_status == "pending":
            query = query.where(Interview.feedback_submitted_at.is_(None))
        elif feedback_status == "submitted":
            query = query.where(Interview.feedback_submitted_at.isnot(None))

        result = await self.db.execute(query)
        return result.scalar_one_or_none() or 0