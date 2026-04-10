from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(32), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True)
    hashed_password = Column(String(128), nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(String(32), nullable=False, default="Interviewer")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)

    # Relationship to jobs where this user is the hiring manager
    jobs = relationship("Job", back_populates="hiring_manager", lazy="selectin")

    # Relationship to interviews where this user is the interviewer
    interviews = relationship("Interview", back_populates="interviewer", lazy="selectin")

    # Relationship to audit logs created by this user
    audit_logs = relationship("AuditLog", back_populates="user", lazy="selectin")

    # Relationship to offers created by this user
    offers = relationship("Offer", back_populates="created_by_user", lazy="selectin", foreign_keys="[Offer.created_by]")

    @property
    def name(self) -> str:
        return self.full_name or self.username

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"