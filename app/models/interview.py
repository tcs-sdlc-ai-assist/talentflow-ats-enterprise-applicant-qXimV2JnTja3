from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    interviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    feedback_rating = Column(Integer, nullable=True)
    feedback_notes = Column(Text, nullable=True)
    feedback_submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    application = relationship("Application", back_populates="interviews", lazy="selectin")
    interviewer = relationship("User", back_populates="interviews", lazy="selectin")


class InterviewFeedback(Base):
    __tablename__ = "interview_feedbacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    notes = Column(Text, nullable=True)
    submitted_at = Column(DateTime, server_default=func.now(), nullable=False)

    interview = relationship("Interview", lazy="selectin")