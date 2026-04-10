from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaginationMeta(BaseModel):
    total: int = Field(..., description="Total number of records")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Records per page")
    total_pages: int = Field(..., description="Total number of pages")

    model_config = ConfigDict(from_attributes=True)


class JobFilterParams(BaseModel):
    status: Optional[str] = Field(None, description="Filter by job status")
    department: Optional[str] = Field(None, description="Filter by department")
    location: Optional[str] = Field(None, description="Filter by location")
    job_type: Optional[str] = Field(None, description="Filter by job type")
    search: Optional[str] = Field(None, description="Search in title and description")
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Records per page")

    model_config = ConfigDict(from_attributes=True)


class JobBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="Job title")
    department: str = Field(..., min_length=1, max_length=100, description="Department name")
    location: str = Field(..., min_length=1, max_length=100, description="Job location")
    type: str = Field(..., min_length=1, max_length=50, description="Job type (Full-Time, Part-Time, Contract, etc.)")
    salary_min: int = Field(..., gt=0, description="Minimum salary")
    salary_max: int = Field(..., gt=0, description="Maximum salary")
    description: str = Field(..., min_length=1, description="Job description")

    @field_validator("salary_max")
    @classmethod
    def salary_max_gte_min(cls, v: int, info) -> int:
        salary_min = info.data.get("salary_min")
        if salary_min is not None and v < salary_min:
            raise ValueError("salary_max must be greater than or equal to salary_min")
        return v

    model_config = ConfigDict(from_attributes=True)


class JobCreate(JobBase):
    hiring_manager_id: int = Field(..., description="ID of the hiring manager")


class JobUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100, description="Job title")
    department: Optional[str] = Field(None, min_length=1, max_length=100, description="Department name")
    location: Optional[str] = Field(None, min_length=1, max_length=100, description="Job location")
    type: Optional[str] = Field(None, min_length=1, max_length=50, description="Job type")
    salary_min: Optional[int] = Field(None, gt=0, description="Minimum salary")
    salary_max: Optional[int] = Field(None, gt=0, description="Maximum salary")
    description: Optional[str] = Field(None, min_length=1, description="Job description")
    hiring_manager_id: Optional[int] = Field(None, description="ID of the hiring manager")

    @field_validator("salary_max")
    @classmethod
    def salary_max_gte_min(cls, v: Optional[int], info) -> Optional[int]:
        if v is None:
            return v
        salary_min = info.data.get("salary_min")
        if salary_min is not None and v < salary_min:
            raise ValueError("salary_max must be greater than or equal to salary_min")
        return v

    model_config = ConfigDict(from_attributes=True)


class JobStatusUpdate(BaseModel):
    status: str = Field(..., description="New job status")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"Draft", "Published", "Closed"}
        if v not in allowed:
            raise ValueError(f"Invalid status '{v}'. Allowed values: {', '.join(sorted(allowed))}")
        return v

    model_config = ConfigDict(from_attributes=True)


class HiringManagerBrief(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    id: int
    title: str
    department: str
    location: str
    type: str
    salary_min: int
    salary_max: int
    description: str
    status: str
    hiring_manager_id: int
    hiring_manager: Optional[HiringManagerBrief] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class JobBriefResponse(BaseModel):
    id: int
    title: str
    department: str
    location: str
    type: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobListResponse(BaseModel):
    items: list[JobBriefResponse]
    pagination: PaginationMeta

    model_config = ConfigDict(from_attributes=True)