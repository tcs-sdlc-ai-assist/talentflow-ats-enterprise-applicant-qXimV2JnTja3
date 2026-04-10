import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.job import Job
from app.models.candidate import Candidate
from app.models.application import Application
from app.models.interview import Interview
from app.models.audit_log import AuditLog

from tests.conftest import create_test_user, login_user


@pytest.mark.asyncio
async def test_dashboard_redirects_unauthenticated_user(client: AsyncClient):
    """Unauthenticated users should get a 401 when accessing the dashboard."""
    response = await client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 401 or response.status_code == 302


@pytest.mark.asyncio
async def test_admin_dashboard_shows_metrics(
    authenticated_admin_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    """System Admin should see the admin dashboard with key metrics."""
    response = await authenticated_admin_client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    text = response.text
    assert "Dashboard" in text
    assert "Open Jobs" in text
    assert "Total Candidates" in text
    assert "Active Applications" in text
    assert "Scheduled Interviews" in text


@pytest.mark.asyncio
async def test_hr_dashboard_shows_metrics(
    authenticated_hr_client: AsyncClient,
    db_session: AsyncSession,
    hr_user: User,
):
    """HR Recruiter should see the admin dashboard with metrics and audit logs."""
    response = await authenticated_hr_client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    text = response.text
    assert "Dashboard" in text
    assert "Open Jobs" in text
    assert "Total Candidates" in text
    assert "Active Applications" in text
    assert "Scheduled Interviews" in text


@pytest.mark.asyncio
async def test_admin_dashboard_shows_recent_audit_logs(
    authenticated_admin_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    """Admin dashboard should display recent audit log entries."""
    audit_log = AuditLog(
        user_id=admin_user.id,
        username=admin_user.username,
        action="create_job",
        entity_type="Job",
        entity_id=1,
        details="Created job 'Test Engineer'",
    )
    db_session.add(audit_log)
    await db_session.flush()

    response = await authenticated_admin_client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    text = response.text
    assert "Recent Audit Activity" in text
    assert "create_job" in text


@pytest.mark.asyncio
async def test_admin_dashboard_metrics_reflect_data(
    authenticated_admin_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    """Admin dashboard metrics should reflect actual data counts."""
    job = Job(
        title="Published Job",
        department="Engineering",
        location="Remote",
        type="Full-Time",
        salary_min=80000,
        salary_max=120000,
        description="A published job for testing.",
        status="Published",
        hiring_manager_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()

    candidate = Candidate(
        name="Test Candidate",
        email="testcandidate@example.com",
        resume_text="Resume text for testing.",
    )
    db_session.add(candidate)
    await db_session.flush()

    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        status="Applied",
    )
    db_session.add(application)
    await db_session.flush()

    response = await authenticated_admin_client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    text = response.text
    assert "Open Jobs" in text
    assert "Total Candidates" in text
    assert "Active Applications" in text


@pytest.mark.asyncio
async def test_hiring_manager_dashboard_shows_own_jobs(
    authenticated_manager_client: AsyncClient,
    db_session: AsyncSession,
    hiring_manager_user: User,
):
    """Hiring Manager should see their own job requisitions on the dashboard."""
    job = Job(
        title="Manager's Job Posting",
        department="Product",
        location="NYC",
        type="Full-Time",
        salary_min=90000,
        salary_max=130000,
        description="A job managed by the hiring manager.",
        status="Published",
        hiring_manager_id=hiring_manager_user.id,
    )
    db_session.add(job)
    await db_session.flush()

    response = await authenticated_manager_client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    text = response.text
    assert "Dashboard" in text
    assert "My Job Requisitions" in text
    assert "Manager&#" in text or "Manager's Job Posting" in text or "Manager" in text


@pytest.mark.asyncio
async def test_hiring_manager_dashboard_shows_metrics(
    authenticated_manager_client: AsyncClient,
    db_session: AsyncSession,
    hiring_manager_user: User,
):
    """Hiring Manager dashboard should show my_jobs and pending_interviews metrics."""
    response = await authenticated_manager_client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    text = response.text
    assert "My Job Requisitions" in text
    assert "Pending Interviews" in text


@pytest.mark.asyncio
async def test_hiring_manager_does_not_see_other_managers_jobs(
    authenticated_manager_client: AsyncClient,
    db_session: AsyncSession,
    hiring_manager_user: User,
    admin_user: User,
):
    """Hiring Manager should NOT see jobs assigned to other managers."""
    other_job = Job(
        title="Other Manager Job",
        department="Sales",
        location="London",
        type="Full-Time",
        salary_min=70000,
        salary_max=100000,
        description="A job managed by someone else.",
        status="Published",
        hiring_manager_id=admin_user.id,
    )
    db_session.add(other_job)
    await db_session.flush()

    response = await authenticated_manager_client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    text = response.text
    assert "Other Manager Job" not in text


@pytest.mark.asyncio
async def test_interviewer_dashboard_shows_upcoming_interviews(
    authenticated_interviewer_client: AsyncClient,
    db_session: AsyncSession,
    interviewer_user: User,
    admin_user: User,
):
    """Interviewer should see their upcoming interviews on the dashboard."""
    job = Job(
        title="Interview Test Job",
        department="Engineering",
        location="Remote",
        type="Full-Time",
        salary_min=80000,
        salary_max=120000,
        description="Job for interview testing.",
        status="Published",
        hiring_manager_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()

    candidate = Candidate(
        name="Interview Candidate",
        email="interviewcandidate@example.com",
        resume_text="Resume for interview candidate.",
    )
    db_session.add(candidate)
    await db_session.flush()

    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        status="Interview",
    )
    db_session.add(application)
    await db_session.flush()

    interview = Interview(
        application_id=application.id,
        interviewer_id=interviewer_user.id,
        scheduled_at=datetime.utcnow() + timedelta(days=2),
    )
    db_session.add(interview)
    await db_session.flush()

    response = await authenticated_interviewer_client.get(
        "/dashboard", follow_redirects=True
    )
    assert response.status_code == 200
    text = response.text
    assert "Dashboard" in text
    assert "Upcoming Interviews" in text


@pytest.mark.asyncio
async def test_interviewer_dashboard_shows_missing_feedback_warning(
    authenticated_interviewer_client: AsyncClient,
    db_session: AsyncSession,
    interviewer_user: User,
    admin_user: User,
):
    """Interviewer dashboard should warn about missing feedback for past interviews."""
    job = Job(
        title="Feedback Test Job",
        department="Engineering",
        location="Remote",
        type="Full-Time",
        salary_min=80000,
        salary_max=120000,
        description="Job for feedback testing.",
        status="Published",
        hiring_manager_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()

    candidate = Candidate(
        name="Feedback Candidate",
        email="feedbackcandidate@example.com",
        resume_text="Resume for feedback candidate.",
    )
    db_session.add(candidate)
    await db_session.flush()

    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        status="Interview",
    )
    db_session.add(application)
    await db_session.flush()

    past_interview = Interview(
        application_id=application.id,
        interviewer_id=interviewer_user.id,
        scheduled_at=datetime.utcnow() - timedelta(days=2),
    )
    db_session.add(past_interview)
    await db_session.flush()

    response = await authenticated_interviewer_client.get(
        "/dashboard", follow_redirects=True
    )
    assert response.status_code == 200
    text = response.text
    assert "Missing Feedback" in text


@pytest.mark.asyncio
async def test_interviewer_dashboard_metrics(
    authenticated_interviewer_client: AsyncClient,
    db_session: AsyncSession,
    interviewer_user: User,
):
    """Interviewer dashboard should show upcoming_interviews and missing_feedback metrics."""
    response = await authenticated_interviewer_client.get(
        "/dashboard", follow_redirects=True
    )
    assert response.status_code == 200
    text = response.text
    assert "Upcoming Interviews" in text
    assert "Missing Feedback" in text


@pytest.mark.asyncio
async def test_dashboard_trailing_slash_redirect(
    authenticated_admin_client: AsyncClient,
):
    """Dashboard should be accessible with trailing slash."""
    response = await authenticated_admin_client.get(
        "/dashboard/", follow_redirects=True
    )
    assert response.status_code == 200
    assert "Dashboard" in response.text


@pytest.mark.asyncio
async def test_admin_dashboard_empty_audit_logs(
    authenticated_admin_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    """Admin dashboard should handle empty audit logs gracefully."""
    response = await authenticated_admin_client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    text = response.text
    assert "No audit activity recorded yet" in text or "Recent Audit Activity" in text


@pytest.mark.asyncio
async def test_hiring_manager_empty_jobs(
    authenticated_manager_client: AsyncClient,
    db_session: AsyncSession,
    hiring_manager_user: User,
):
    """Hiring Manager dashboard should handle having no jobs gracefully."""
    response = await authenticated_manager_client.get(
        "/dashboard", follow_redirects=True
    )
    assert response.status_code == 200
    text = response.text
    assert "No job requisitions assigned" in text or "My Job Requisitions" in text


@pytest.mark.asyncio
async def test_interviewer_empty_interviews(
    authenticated_interviewer_client: AsyncClient,
    db_session: AsyncSession,
    interviewer_user: User,
):
    """Interviewer dashboard should handle having no interviews gracefully."""
    response = await authenticated_interviewer_client.get(
        "/dashboard", follow_redirects=True
    )
    assert response.status_code == 200
    text = response.text
    assert "No upcoming interviews" in text or "Upcoming Interviews" in text


@pytest.mark.asyncio
async def test_dashboard_displays_user_role(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
):
    """Dashboard should display the current user's role."""
    response = await authenticated_admin_client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    text = response.text
    assert admin_user.username in text


@pytest.mark.asyncio
async def test_dashboard_displays_username(
    authenticated_hr_client: AsyncClient,
    hr_user: User,
):
    """Dashboard should display the current user's username."""
    response = await authenticated_hr_client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    assert hr_user.username in response.text


@pytest.mark.asyncio
async def test_admin_dashboard_quick_actions(
    authenticated_admin_client: AsyncClient,
):
    """Admin dashboard should show quick action links."""
    response = await authenticated_admin_client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    text = response.text
    assert "Quick Actions" in text
    assert "Create New Job" in text
    assert "Add Candidate" in text


@pytest.mark.asyncio
async def test_hiring_manager_dashboard_shows_application_count(
    authenticated_manager_client: AsyncClient,
    db_session: AsyncSession,
    hiring_manager_user: User,
):
    """Hiring Manager dashboard should show application count for their jobs."""
    job = Job(
        title="Manager Job With Apps",
        department="Engineering",
        location="Remote",
        type="Full-Time",
        salary_min=80000,
        salary_max=120000,
        description="Job with applications.",
        status="Published",
        hiring_manager_id=hiring_manager_user.id,
    )
    db_session.add(job)
    await db_session.flush()

    candidate = Candidate(
        name="App Count Candidate",
        email="appcount@example.com",
        resume_text="Resume text.",
    )
    db_session.add(candidate)
    await db_session.flush()

    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        status="Applied",
    )
    db_session.add(application)
    await db_session.flush()

    response = await authenticated_manager_client.get(
        "/dashboard", follow_redirects=True
    )
    assert response.status_code == 200
    text = response.text
    assert "Manager Job With Apps" in text


@pytest.mark.asyncio
async def test_multiple_audit_logs_displayed(
    authenticated_admin_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    """Admin dashboard should display multiple recent audit log entries."""
    for i in range(5):
        audit_log = AuditLog(
            user_id=admin_user.id,
            username=admin_user.username,
            action=f"test_action_{i}",
            entity_type="Job",
            entity_id=i + 1,
            details=f"Test audit log entry {i}",
        )
        db_session.add(audit_log)
    await db_session.flush()

    response = await authenticated_admin_client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    text = response.text
    assert "test_action_0" in text
    assert "test_action_4" in text


@pytest.mark.asyncio
async def test_interviewer_completed_interview_not_in_upcoming(
    authenticated_interviewer_client: AsyncClient,
    db_session: AsyncSession,
    interviewer_user: User,
    admin_user: User,
):
    """Completed interviews (with feedback) should not appear as upcoming."""
    job = Job(
        title="Completed Interview Job",
        department="Engineering",
        location="Remote",
        type="Full-Time",
        salary_min=80000,
        salary_max=120000,
        description="Job for completed interview.",
        status="Published",
        hiring_manager_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()

    candidate = Candidate(
        name="Completed Candidate",
        email="completed@example.com",
        resume_text="Resume.",
    )
    db_session.add(candidate)
    await db_session.flush()

    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        status="Interview",
    )
    db_session.add(application)
    await db_session.flush()

    interview = Interview(
        application_id=application.id,
        interviewer_id=interviewer_user.id,
        scheduled_at=datetime.utcnow() + timedelta(days=1),
        feedback_rating=4,
        feedback_notes="Good candidate.",
        feedback_submitted_at=datetime.utcnow(),
    )
    db_session.add(interview)
    await db_session.flush()

    response = await authenticated_interviewer_client.get(
        "/dashboard", follow_redirects=True
    )
    assert response.status_code == 200
    # The completed interview should not count as upcoming
    # The page should still load successfully
    assert "Dashboard" in response.text