import logging
from typing import Optional

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.candidate import Candidate, Skill, candidate_skills
from app.models.application import Application
from app.models.user import User
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


class CandidateService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_candidate(
        self,
        name: str,
        email: str,
        resume_text: str,
        user: User,
        phone: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        skill_names: Optional[list[str]] = None,
        skill_ids: Optional[list[int]] = None,
    ) -> Candidate:
        existing_result = await self.db.execute(
            select(Candidate).where(Candidate.email == email.strip().lower())
        )
        existing = existing_result.scalars().first()
        if existing is not None:
            raise ValueError(f"A candidate with email '{email}' already exists.")

        candidate = Candidate(
            name=name.strip(),
            email=email.strip().lower(),
            resume_text=resume_text.strip(),
            phone=phone.strip() if phone else None,
            linkedin_url=linkedin_url.strip() if linkedin_url else None,
        )

        self.db.add(candidate)
        await self.db.flush()

        if skill_names:
            await self._set_skills_by_names(candidate, skill_names)
        elif skill_ids:
            await self._set_skills_by_ids(candidate, skill_ids)

        await self.db.flush()
        await self.db.refresh(candidate)

        await audit_service.log_action(
            db=self.db,
            user_id=user.id,
            username=user.username,
            action="create_candidate",
            entity_type="Candidate",
            entity_id=candidate.id,
            details=f"Created candidate '{candidate.name}' ({candidate.email})",
        )

        logger.info(
            "Candidate created: id=%d name='%s' email='%s' by user=%s",
            candidate.id,
            candidate.name,
            candidate.email,
            user.username,
        )
        return candidate

    async def update_candidate(
        self,
        candidate_id: int,
        user: User,
        name: Optional[str] = None,
        email: Optional[str] = None,
        resume_text: Optional[str] = None,
        phone: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        skill_names: Optional[list[str]] = None,
        skill_ids: Optional[list[int]] = None,
    ) -> Candidate:
        candidate = await self.get_candidate_by_id(candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate with id {candidate_id} not found.")

        if email is not None:
            normalized_email = email.strip().lower()
            if normalized_email != candidate.email:
                existing_result = await self.db.execute(
                    select(Candidate).where(
                        Candidate.email == normalized_email,
                        Candidate.id != candidate_id,
                    )
                )
                existing = existing_result.scalars().first()
                if existing is not None:
                    raise ValueError(f"A candidate with email '{normalized_email}' already exists.")
                candidate.email = normalized_email

        if name is not None:
            candidate.name = name.strip()

        if resume_text is not None:
            candidate.resume_text = resume_text.strip()

        if phone is not None:
            candidate.phone = phone.strip() if phone.strip() else None

        if linkedin_url is not None:
            candidate.linkedin_url = linkedin_url.strip() if linkedin_url.strip() else None

        if skill_names is not None:
            await self._set_skills_by_names(candidate, skill_names)
        elif skill_ids is not None:
            await self._set_skills_by_ids(candidate, skill_ids)

        await self.db.flush()
        await self.db.refresh(candidate)

        await audit_service.log_action(
            db=self.db,
            user_id=user.id,
            username=user.username,
            action="update_candidate",
            entity_type="Candidate",
            entity_id=candidate.id,
            details=f"Updated candidate '{candidate.name}' ({candidate.email})",
        )

        logger.info(
            "Candidate updated: id=%d name='%s' by user=%s",
            candidate.id,
            candidate.name,
            user.username,
        )
        return candidate

    async def get_candidate_by_id(self, candidate_id: int) -> Optional[Candidate]:
        result = await self.db.execute(
            select(Candidate)
            .options(
                selectinload(Candidate.skills),
                selectinload(Candidate.applications).selectinload(Application.job),
            )
            .where(Candidate.id == candidate_id)
        )
        return result.scalars().first()

    async def list_candidates(
        self,
        search: Optional[str] = None,
        skill_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        query = select(Candidate).options(selectinload(Candidate.skills))
        count_query = select(func.count()).select_from(Candidate)

        if search:
            search_term = f"%{search.strip()}%"
            search_filter = or_(
                Candidate.name.ilike(search_term),
                Candidate.email.ilike(search_term),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        if skill_id is not None:
            query = query.join(candidate_skills).where(
                candidate_skills.c.skill_id == skill_id
            )
            count_query = (
                select(func.count(func.distinct(Candidate.id)))
                .select_from(Candidate)
                .join(candidate_skills)
                .where(candidate_skills.c.skill_id == skill_id)
            )
            if search:
                search_term = f"%{search.strip()}%"
                search_filter = or_(
                    Candidate.name.ilike(search_term),
                    Candidate.email.ilike(search_term),
                )
                count_query = count_query.where(search_filter)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(Candidate.created_at.desc())
        query = query.offset(offset).limit(page_size)

        result = await self.db.execute(query)
        candidates = list(result.scalars().unique().all())

        total_pages = max(1, (total + page_size - 1) // page_size)

        return {
            "items": candidates,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    async def get_all_skills(self) -> list[Skill]:
        result = await self.db.execute(
            select(Skill).order_by(Skill.name.asc())
        )
        return list(result.scalars().all())

    async def get_or_create_skill(self, skill_name: str) -> Skill:
        normalized = skill_name.strip()
        if not normalized:
            raise ValueError("Skill name cannot be empty.")

        result = await self.db.execute(
            select(Skill).where(func.lower(Skill.name) == normalized.lower())
        )
        skill = result.scalars().first()

        if skill is None:
            skill = Skill(name=normalized)
            self.db.add(skill)
            await self.db.flush()
            await self.db.refresh(skill)
            logger.info("Created new skill: id=%d name='%s'", skill.id, skill.name)

        return skill

    async def _set_skills_by_names(self, candidate: Candidate, skill_names: list[str]) -> None:
        skills = []
        for name in skill_names:
            name = name.strip()
            if name:
                skill = await self.get_or_create_skill(name)
                skills.append(skill)
        candidate.skills = skills

    async def _set_skills_by_ids(self, candidate: Candidate, skill_ids: list[int]) -> None:
        if not skill_ids:
            candidate.skills = []
            return

        result = await self.db.execute(
            select(Skill).where(Skill.id.in_(skill_ids))
        )
        skills = list(result.scalars().all())
        candidate.skills = skills

    async def add_skill_to_candidate(
        self,
        candidate_id: int,
        skill_name: str,
        user: User,
    ) -> Candidate:
        candidate = await self.get_candidate_by_id(candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate with id {candidate_id} not found.")

        skill = await self.get_or_create_skill(skill_name)

        existing_skill_ids = {s.id for s in candidate.skills}
        if skill.id not in existing_skill_ids:
            candidate.skills.append(skill)
            await self.db.flush()

            await audit_service.log_action(
                db=self.db,
                user_id=user.id,
                username=user.username,
                action="add_candidate_skill",
                entity_type="Candidate",
                entity_id=candidate.id,
                details=f"Added skill '{skill.name}' to candidate '{candidate.name}'",
            )

            logger.info(
                "Added skill '%s' to candidate id=%d by user=%s",
                skill.name,
                candidate.id,
                user.username,
            )

        await self.db.refresh(candidate)
        return candidate

    async def remove_skill_from_candidate(
        self,
        candidate_id: int,
        skill_id: int,
        user: User,
    ) -> Candidate:
        candidate = await self.get_candidate_by_id(candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate with id {candidate_id} not found.")

        skill_to_remove = None
        for skill in candidate.skills:
            if skill.id == skill_id:
                skill_to_remove = skill
                break

        if skill_to_remove is not None:
            candidate.skills.remove(skill_to_remove)
            await self.db.flush()

            await audit_service.log_action(
                db=self.db,
                user_id=user.id,
                username=user.username,
                action="remove_candidate_skill",
                entity_type="Candidate",
                entity_id=candidate.id,
                details=f"Removed skill '{skill_to_remove.name}' from candidate '{candidate.name}'",
            )

            logger.info(
                "Removed skill '%s' from candidate id=%d by user=%s",
                skill_to_remove.name,
                candidate.id,
                user.username,
            )

        await self.db.refresh(candidate)
        return candidate