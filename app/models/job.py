from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    location = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)
    salary_min = Column(Integer, nullable=False)
    salary_max = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="Draft")
    hiring_manager_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    hiring_manager = relationship("User", back_populates="jobs", lazy="selectin")
    applications = relationship("Application", back_populates="job", lazy="selectin")