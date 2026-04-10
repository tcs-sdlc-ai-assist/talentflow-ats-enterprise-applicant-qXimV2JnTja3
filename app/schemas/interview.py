from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class InterviewCreate(BaseModel):
    application_id: int
    interviewer_id: int
    scheduled_at: datetime

    @field_validator("application_id")
    @classmethod
    def application_id_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("application_id must be a positive integer")
        return v

    @field_validator("interviewer_id")
    @classmethod
    def interviewer_id_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("interviewer_id must be a positive integer")
        return v


class FeedbackSubmit(BaseModel):
    feedback_rating: int
    feedback_notes: str

    @field_validator("feedback_rating")
    @classmethod
    def rating_in_range(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("feedback_rating must be between 1 and 5")
        return v

    @field_validator("feedback_notes")
    @classmethod
    def notes_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("feedback_notes must not be empty")
        return v.strip()


class InterviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    interviewer_id: int
    scheduled_at: datetime
    feedback_rating: Optional[int] = None
    feedback_notes: Optional[str] = None
    feedback_submitted_at: Optional[datetime] = None


class InterviewListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[InterviewResponse]
    total: int