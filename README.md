# TalentFlow ATS

An Applicant Tracking System built with Python and FastAPI for managing the full recruitment lifecycle — from job posting to candidate hiring.

## Features

- **Job Management** — Create, update, and manage job postings with detailed descriptions, requirements, and status tracking
- **Candidate Tracking** — Track candidates through customizable hiring pipelines with stage-based workflows
- **Application Processing** — Receive and process applications with resume parsing and automated screening
- **Interview Scheduling** — Schedule and manage interviews with calendar integration and interviewer assignment
- **Feedback Collection** — Structured interview feedback and scoring with collaborative evaluation tools
- **Role-Based Access Control** — Granular permissions for recruiters, hiring managers, interviewers, and admins
- **Audit Logging** — Comprehensive activity tracking for compliance and reporting
- **Dashboard & Analytics** — Real-time metrics on hiring pipeline, time-to-hire, and recruiter performance

## Tech Stack

- **Backend:** Python 3.11+, FastAPI
- **Database:** SQLAlchemy 2.0 (async) with SQLite (aiosqlite) / PostgreSQL (asyncpg)
- **Authentication:** JWT (python-jose) with bcrypt password hashing
- **Validation:** Pydantic v2 with email-validator
- **Templating:** Jinja2 with Tailwind CSS
- **Testing:** pytest, pytest-asyncio, httpx

## Project Structure

```
talentflow-ats/
├── app/
│   ├── core/
│   │   ├── config.py          # Application settings (BaseSettings)
│   │   ├── database.py        # Async SQLAlchemy engine & session
│   │   ├── security.py        # JWT token creation & password hashing
│   │   └── __init__.py
│   ├── models/
│   │   ├── user.py            # User model
│   │   ├── job.py             # Job posting model
│   │   ├── candidate.py       # Candidate model & association tables
│   │   ├── application.py     # Application model
│   │   ├── interview.py       # Interview, assignment & feedback models
│   │   ├── audit_log.py       # Audit log model
│   │   └── __init__.py
│   ├── schemas/
│   │   ├── user.py            # User request/response schemas
│   │   ├── job.py             # Job request/response schemas
│   │   ├── candidate.py       # Candidate request/response schemas
│   │   ├── application.py     # Application request/response schemas
│   │   ├── interview.py       # Interview request/response schemas
│   │   └── __init__.py
│   ├── services/
│   │   ├── user.py            # User business logic
│   │   ├── job.py             # Job business logic
│   │   ├── candidate.py       # Candidate business logic
│   │   ├── application.py     # Application business logic
│   │   ├── interview.py       # Interview business logic
│   │   ├── audit.py           # Audit logging service
│   │   └── __init__.py
│   ├── routers/
│   │   ├── auth.py            # Authentication routes (login, register, logout)
│   │   ├── users.py           # User management routes
│   │   ├── jobs.py            # Job posting routes
│   │   ├── candidates.py      # Candidate routes
│   │   ├── applications.py    # Application routes
│   │   ├── interviews.py      # Interview routes
│   │   ├── dashboard.py       # Dashboard & analytics routes
│   │   └── __init__.py
│   ├── dependencies/
│   │   ├── auth.py            # Auth dependency (get_current_user)
│   │   └── __init__.py
│   ├── templates/             # Jinja2 HTML templates with Tailwind CSS
│   │   ├── base.html
│   │   ├── auth/
│   │   ├── dashboard/
│   │   ├── jobs/
│   │   ├── candidates/
│   │   ├── applications/
│   │   └── interviews/
│   └── main.py                # FastAPI app entry point
├── tests/
│   ├── test_auth.py
│   ├── test_jobs.py
│   ├── test_candidates.py
│   ├── test_applications.py
│   └── test_interviews.py
├── .env                       # Environment variables (not committed)
├── requirements.txt           # Python dependencies
└── README.md
```

## Setup Instructions

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd talentflow-ats
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Application
APP_NAME=TalentFlow ATS
DEBUG=true

# Database
DATABASE_URL=sqlite+aiosqlite:///./talentflow.db

# JWT Authentication
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
```

### 5. Run the Application

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at:
- **Web UI:** http://localhost:8000
- **API Docs (Swagger):** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### 6. Run Tests

```bash
pytest tests/ -v
```

## API Routes Summary

### Authentication
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Login and receive JWT token |
| POST | `/api/auth/logout` | Logout (invalidate token) |

### Users
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/users` | List all users (admin only) |
| GET | `/api/users/{id}` | Get user by ID |
| PUT | `/api/users/{id}` | Update user profile |
| DELETE | `/api/users/{id}` | Deactivate user (admin only) |

### Jobs
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/jobs` | List all job postings |
| POST | `/api/jobs` | Create a new job posting |
| GET | `/api/jobs/{id}` | Get job details |
| PUT | `/api/jobs/{id}` | Update job posting |
| DELETE | `/api/jobs/{id}` | Archive job posting |

### Candidates
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/candidates` | List all candidates |
| POST | `/api/candidates` | Create a new candidate |
| GET | `/api/candidates/{id}` | Get candidate details |
| PUT | `/api/candidates/{id}` | Update candidate info |

### Applications
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/applications` | List all applications |
| POST | `/api/applications` | Submit a new application |
| GET | `/api/applications/{id}` | Get application details |
| PUT | `/api/applications/{id}` | Update application status/stage |

### Interviews
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/interviews` | List all interviews |
| POST | `/api/interviews` | Schedule a new interview |
| GET | `/api/interviews/{id}` | Get interview details |
| PUT | `/api/interviews/{id}` | Update interview |
| POST | `/api/interviews/{id}/feedback` | Submit interview feedback |

### Dashboard
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/dashboard/stats` | Get hiring pipeline statistics |
| GET | `/api/dashboard/metrics` | Get recruiter performance metrics |

## User Roles

| Role | Description | Permissions |
|------|-------------|-------------|
| **Admin** | System administrator | Full access to all resources, user management, system configuration |
| **Recruiter** | Recruitment team member | Create/manage jobs, candidates, applications, schedule interviews |
| **Hiring Manager** | Department hiring lead | View jobs, review applications, provide interview feedback, make hiring decisions |
| **Interviewer** | Interview panel member | View assigned interviews, submit feedback and scores |
| **Viewer** | Read-only access | View jobs, candidates, and application statuses |

## Deployment Notes

### Production Configuration

1. **Database:** Switch to PostgreSQL by updating `DATABASE_URL`:
   ```env
   DATABASE_URL=postgresql+asyncpg://user:password@host:5432/talentflow
   ```

2. **Secret Key:** Generate a strong secret key:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

3. **CORS Origins:** Restrict to your production domain:
   ```env
   CORS_ORIGINS=["https://your-domain.com"]
   ```

4. **Debug Mode:** Disable debug mode:
   ```env
   DEBUG=false
   ```

### Running with Gunicorn (Production)

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## License

Private — All rights reserved.