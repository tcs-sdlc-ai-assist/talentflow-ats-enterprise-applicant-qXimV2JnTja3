from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class SkillInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CandidateCreate(BaseModel):
    name: str
    email: str
    resume_text: str
    linkedin_url: Optional[str] = None
    skill_ids: Optional[list[int]] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Candidate name is required")
        if len(v) > 100:
            raise ValueError("Candidate name must be at most 100 characters")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("Email is required")
        if len(v) > 100:
            raise ValueError("Email must be at most 100 characters")
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v

    @field_validator("resume_text")
    @classmethod
    def validate_resume_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Resume text is required")
        return v

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 200:
            raise ValueError("LinkedIn URL must be at most 200 characters")
        return v


class CandidateUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    resume_text: Optional[str] = None
    linkedin_url: Optional[str] = None
    skill_ids: Optional[list[int]] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Candidate name cannot be empty")
        if len(v) > 100:
            raise ValueError("Candidate name must be at most 100 characters")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        if not v:
            raise ValueError("Email cannot be empty")
        if len(v) > 100:
            raise ValueError("Email must be at most 100 characters")
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v

    @field_validator("resume_text")
    @classmethod
    def validate_resume_text(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Resume text cannot be empty")
        return v

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 200:
            raise ValueError("LinkedIn URL must be at most 200 characters")
        return v


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    resume_text: str
    linkedin_url: Optional[str] = None
    skills: list[SkillInfo] = []
    created_at: datetime


class CandidateListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[CandidateResponse]
    total: int
    page: int
    page_size: int