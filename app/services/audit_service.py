import logging
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.schemas.audit_log import (
    AuditLogCreate,
    AuditLogFilterParams,
    AuditLogListResponse,
    AuditLogResponse,
    PaginationResponse,
)

logger = logging.getLogger(__name__)


class AuditTrailService:

    async def log_action(
        self,
        db: AsyncSession,
        user_id: int,
        username: str,
        action: str,
        entity_type: str,
        entity_id: int,
        details: Optional[str] = None,
    ) -> AuditLog:
        audit_entry = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
        db.add(audit_entry)
        await db.flush()
        await db.refresh(audit_entry)
        logger.info(
            "Audit log created: user_id=%d action=%s entity_type=%s entity_id=%d",
            user_id,
            action,
            entity_type,
            entity_id,
        )
        return audit_entry

    async def list_logs(
        self,
        db: AsyncSession,
        filters: AuditLogFilterParams,
    ) -> AuditLogListResponse:
        query = select(AuditLog)
        count_query = select(func.count()).select_from(AuditLog)

        if filters.user_id is not None:
            query = query.where(AuditLog.user_id == filters.user_id)
            count_query = count_query.where(AuditLog.user_id == filters.user_id)

        if filters.action is not None:
            query = query.where(AuditLog.action == filters.action)
            count_query = count_query.where(AuditLog.action == filters.action)

        if filters.entity_type is not None:
            query = query.where(AuditLog.entity_type == filters.entity_type)
            count_query = count_query.where(AuditLog.entity_type == filters.entity_type)

        if filters.entity_id is not None:
            query = query.where(AuditLog.entity_id == filters.entity_id)
            count_query = count_query.where(AuditLog.entity_id == filters.entity_id)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (filters.page - 1) * filters.page_size
        query = query.order_by(AuditLog.timestamp.desc())
        query = query.offset(offset).limit(filters.page_size)

        result = await db.execute(query)
        logs = result.scalars().all()

        log_responses = [AuditLogResponse.model_validate(log) for log in logs]

        return AuditLogListResponse(
            logs=log_responses,
            pagination=PaginationResponse(
                page=filters.page,
                page_size=filters.page_size,
                total=total,
            ),
        )

    async def get_recent_logs(
        self,
        db: AsyncSession,
        limit: int = 10,
    ) -> list[AuditLog]:
        query = (
            select(AuditLog)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())


audit_service = AuditTrailService()