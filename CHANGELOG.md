# Changelog

All notable changes to the TalentFlow ATS project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-01

### Added

#### Authentication & Authorization
- User registration with email validation and secure password hashing
- JWT-based authentication with access token and refresh token support
- Role-based access control (RBAC) with roles: Super Admin, Admin, Hiring Manager, Recruiter, Interviewer, Viewer
- Protected routes with permission-based endpoint guards
- Session management and secure logout

#### Job Management
- Full CRUD operations for job postings
- Job status lifecycle: Draft, Open, On Hold, Closed, Cancelled
- Job detail fields including title, description, department, location, employment type, salary range, and requirements
- Filtering and searching jobs by status, department, and keywords
- Job assignment to hiring managers and recruiters

#### Candidate Management
- Candidate profile creation and management with contact details, resume, and skills
- Candidate search and filtering by name, email, skills, and status
- Candidate profile viewing with full application history
- Duplicate candidate detection by email
- Skills and experience tracking per candidate

#### Application Pipeline & Kanban Board
- Application submission linking candidates to job postings
- Visual Kanban board for tracking application stages
- Configurable pipeline stages: Applied, Screening, Interview, Offer, Hired, Rejected
- Drag-and-drop stage transitions with status validation
- Application notes and activity history
- Bulk application status updates

#### Interview Scheduling & Feedback
- Interview scheduling with date, time, location, and type (phone, video, onsite)
- Interviewer assignment to scheduled interviews
- Structured interview feedback submission with ratings and comments
- Interview status tracking: Scheduled, In Progress, Completed, Cancelled
- Calendar view for upcoming interviews
- Email notification placeholders for interview invitations

#### Dashboards & Reporting
- Overview dashboard with key recruitment metrics
- Active jobs count, open positions, and pipeline summary
- Application statistics by stage and status
- Time-to-hire and conversion rate metrics
- Department-level recruitment summaries
- Role-specific dashboard views

#### Audit Logging
- Comprehensive audit trail for all system actions
- Tracks actor, action type, target entity, and timestamp
- Audit log viewing with filtering by user, action, and date range
- Immutable log entries for compliance and accountability

#### Technical Foundation
- FastAPI backend with async request handling
- SQLAlchemy 2.0 async ORM with SQLite (aiosqlite) database
- Pydantic v2 schemas for request/response validation
- Modular project structure with routers, services, models, and schemas
- CORS middleware configuration
- Structured logging throughout the application
- Lifespan-based startup and shutdown hooks
- Comprehensive error handling with appropriate HTTP status codes