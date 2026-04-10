from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "Applied": ["Screening"],
    "Screening": ["Interview", "Rejected"],
    "Interview": ["Offer", "Rejected"],
    "Offer": ["Hired", "Rejected"],
    "Hired": [],
    "Rejected": [],
}

APPLICATION_STATUSES: list[str] = list(ALLOWED_TRANSITIONS.keys())


class ApplicationCreate(BaseModel):
    candidate_id: int
    job_id: int

    model_config = ConfigDict(strict=True)


class ApplicationStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in APPLICATION_STATUSES:
            raise ValueError(
                f"Invalid status '{v}'. Must be one of: {', '.join(APPLICATION_STATUSES)}"
            )
        return v

    model_config = ConfigDict(strict=True)


class CandidateBrief(BaseModel):
    id: int
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class JobBrief(BaseModel):
    id: int
    title: str
    department: str

    model_config = ConfigDict(from_attributes=True)


class ApplicationResponse(BaseModel):
    id: int
    candidate_id: int
    job_id: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    candidate: Optional[CandidateBrief] = None
    job: Optional[JobBrief] = None

    model_config = ConfigDict(from_attributes=True)


class ApplicationListResponse(BaseModel):
    items: list[ApplicationResponse]
    total: int