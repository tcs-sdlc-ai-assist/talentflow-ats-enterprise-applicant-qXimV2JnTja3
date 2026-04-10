from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuditLogCreate(BaseModel):
    user_id: int
    username: str
    action: str = Field(..., max_length=64)
    entity_type: str = Field(..., max_length=32)
    entity_id: int
    details: Optional[str] = None


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    user_id: int
    username: str
    action: str
    entity_type: str
    entity_id: int
    details: Optional[str] = None


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginationResponse(BaseModel):
    page: int
    page_size: int
    total: int


class AuditLogFilterParams(BaseModel):
    user_id: Optional[int] = None
    action: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 64:
            raise ValueError("Action must be at most 64 characters")
        return v

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 32:
            raise ValueError("Entity type must be at most 32 characters")
        return v


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogResponse]
    pagination: PaginationResponse