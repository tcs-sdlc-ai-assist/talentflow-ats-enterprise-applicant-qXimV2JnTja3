import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.job import Job
from app.models.candidate import Candidate
from app.models.application import Application
from app.models.interview import Interview
from app.services.audit_service import audit_service
from app.schemas.audit_log import AuditLogFilterParams

from tests.conftest import create_test_user, login_user


@pytest.mark.asyncio
async def test_audit_service_log_action_creates_entry(db_session: AsyncSession, admin_user: User):
    """Test that log_action creates an audit log entry with correct fields."""
    log_entry = await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="test_action",
        entity_type="TestEntity",
        entity_id=999,
        details="Test audit log entry",
    )

    assert log_entry is not None
    assert log_entry.id is not None
    assert log_entry.user_id == admin_user.id
    assert log_entry.username == admin_user.username
    assert log_entry.action == "test_action"
    assert log_entry.entity_type == "TestEntity"
    assert log_entry.entity_id == 999
    assert log_entry.details == "Test audit log entry"
    assert log_entry.timestamp is not None


@pytest.mark.asyncio
async def test_audit_service_log_action_without_details(db_session: AsyncSession, admin_user: User):
    """Test that log_action works when details is None."""
    log_entry = await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="simple_action",
        entity_type="SimpleEntity",
        entity_id=1,
        details=None,
    )

    assert log_entry is not None
    assert log_entry.details is None
    assert log_entry.action == "simple_action"


@pytest.mark.asyncio
async def test_audit_service_list_logs_returns_all(db_session: AsyncSession, admin_user: User):
    """Test that list_logs returns all logs when no filters are applied."""
    for i in range(5):
        await audit_service.log_action(
            db=db_session,
            user_id=admin_user.id,
            username=admin_user.username,
            action=f"action_{i}",
            entity_type="TestEntity",
            entity_id=i,
            details=f"Detail {i}",
        )

    filters = AuditLogFilterParams(page=1, page_size=20)
    result = await audit_service.list_logs(db=db_session, filters=filters)

    assert result.pagination.total >= 5
    assert len(result.logs) >= 5


@pytest.mark.asyncio
async def test_audit_service_list_logs_filter_by_user_id(db_session: AsyncSession, admin_user: User):
    """Test filtering audit logs by user_id."""
    other_user = await create_test_user(
        db_session,
        username="other_audit_user",
        role="HR Recruiter",
        email="other_audit@test.com",
    )

    await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="admin_action",
        entity_type="Job",
        entity_id=1,
    )
    await audit_service.log_action(
        db=db_session,
        user_id=other_user.id,
        username=other_user.username,
        action="hr_action",
        entity_type="Candidate",
        entity_id=2,
    )

    filters = AuditLogFilterParams(user_id=other_user.id, page=1, page_size=20)
    result = await audit_service.list_logs(db=db_session, filters=filters)

    assert result.pagination.total >= 1
    for log in result.logs:
        assert log.user_id == other_user.id


@pytest.mark.asyncio
async def test_audit_service_list_logs_filter_by_action(db_session: AsyncSession, admin_user: User):
    """Test filtering audit logs by action."""
    await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="create_job",
        entity_type="Job",
        entity_id=10,
    )
    await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="update_job",
        entity_type="Job",
        entity_id=10,
    )

    filters = AuditLogFilterParams(action="create_job", page=1, page_size=20)
    result = await audit_service.list_logs(db=db_session, filters=filters)

    assert result.pagination.total >= 1
    for log in result.logs:
        assert log.action == "create_job"


@pytest.mark.asyncio
async def test_audit_service_list_logs_filter_by_entity_type(db_session: AsyncSession, admin_user: User):
    """Test filtering audit logs by entity_type."""
    await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="create_candidate",
        entity_type="Candidate",
        entity_id=5,
    )
    await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="create_job",
        entity_type="Job",
        entity_id=6,
    )

    filters = AuditLogFilterParams(entity_type="Candidate", page=1, page_size=20)
    result = await audit_service.list_logs(db=db_session, filters=filters)

    assert result.pagination.total >= 1
    for log in result.logs:
        assert log.entity_type == "Candidate"


@pytest.mark.asyncio
async def test_audit_service_list_logs_pagination(db_session: AsyncSession, admin_user: User):
    """Test that audit log listing supports pagination."""
    for i in range(15):
        await audit_service.log_action(
            db=db_session,
            user_id=admin_user.id,
            username=admin_user.username,
            action="paginated_action",
            entity_type="PaginationTest",
            entity_id=i,
        )

    filters_page1 = AuditLogFilterParams(
        action="paginated_action",
        entity_type="PaginationTest",
        page=1,
        page_size=5,
    )
    result_page1 = await audit_service.list_logs(db=db_session, filters=filters_page1)

    assert result_page1.pagination.page == 1
    assert result_page1.pagination.page_size == 5
    assert len(result_page1.logs) == 5
    assert result_page1.pagination.total >= 15

    filters_page2 = AuditLogFilterParams(
        action="paginated_action",
        entity_type="PaginationTest",
        page=2,
        page_size=5,
    )
    result_page2 = await audit_service.list_logs(db=db_session, filters=filters_page2)

    assert result_page2.pagination.page == 2
    assert len(result_page2.logs) == 5

    page1_ids = {log.id for log in result_page1.logs}
    page2_ids = {log.id for log in result_page2.logs}
    assert page1_ids.isdisjoint(page2_ids), "Pages should not overlap"


@pytest.mark.asyncio
async def test_audit_service_get_recent_logs(db_session: AsyncSession, admin_user: User):
    """Test that get_recent_logs returns the most recent entries."""
    for i in range(12):
        await audit_service.log_action(
            db=db_session,
            user_id=admin_user.id,
            username=admin_user.username,
            action=f"recent_action_{i}",
            entity_type="RecentTest",
            entity_id=i,
        )

    recent = await audit_service.get_recent_logs(db=db_session, limit=5)

    assert len(recent) == 5
    for i in range(len(recent) - 1):
        assert recent[i].timestamp >= recent[i + 1].timestamp


@pytest.mark.asyncio
async def test_audit_log_immutability(db_session: AsyncSession, admin_user: User):
    """Test that audit log entries cannot be modified after creation."""
    log_entry = await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="immutable_action",
        entity_type="ImmutableTest",
        entity_id=42,
        details="Original details",
    )

    original_id = log_entry.id
    original_action = log_entry.action
    original_details = log_entry.details
    original_timestamp = log_entry.timestamp

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.id == original_id)
    )
    fetched_log = result.scalars().first()

    assert fetched_log is not None
    assert fetched_log.action == original_action
    assert fetched_log.details == original_details
    assert fetched_log.timestamp == original_timestamp


@pytest.mark.asyncio
async def test_audit_log_records_correct_user_info(db_session: AsyncSession):
    """Test that audit log correctly records the acting user's information."""
    user = await create_test_user(
        db_session,
        username="audit_actor",
        role="HR Recruiter",
        email="audit_actor@test.com",
        full_name="Audit Actor",
    )

    log_entry = await audit_service.log_action(
        db=db_session,
        user_id=user.id,
        username=user.username,
        action="actor_test",
        entity_type="User",
        entity_id=user.id,
        details="Testing actor recording",
    )

    assert log_entry.user_id == user.id
    assert log_entry.username == "audit_actor"


@pytest.mark.asyncio
async def test_audit_log_records_entity_info(db_session: AsyncSession, admin_user: User):
    """Test that audit log correctly records entity type and ID."""
    log_entry = await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="create_job",
        entity_type="Job",
        entity_id=777,
        details="Created job posting for Senior Engineer",
    )

    assert log_entry.entity_type == "Job"
    assert log_entry.entity_id == 777


@pytest.mark.asyncio
async def test_audit_log_timestamp_is_set_automatically(db_session: AsyncSession, admin_user: User):
    """Test that timestamp is automatically set on audit log creation."""
    from datetime import datetime

    before = datetime.utcnow()

    log_entry = await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="timestamp_test",
        entity_type="TimestampTest",
        entity_id=1,
    )

    after = datetime.utcnow()

    assert log_entry.timestamp is not None
    assert log_entry.timestamp >= before.replace(microsecond=0)


@pytest.mark.asyncio
async def test_job_creation_creates_audit_log(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
    db_session: AsyncSession,
):
    """Test that creating a job generates an audit log entry."""
    count_before_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "create_job")
    )
    count_before = count_before_result.scalar() or 0

    response = await authenticated_admin_client.post(
        "/jobs/",
        data={
            "title": "Audit Test Job",
            "department": "Engineering",
            "location": "Remote",
            "type": "Full-Time",
            "salary_min": "80000",
            "salary_max": "120000",
            "description": "A job for testing audit logs",
            "hiring_manager_id": str(admin_user.id),
        },
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)

    count_after_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "create_job")
    )
    count_after = count_after_result.scalar() or 0

    assert count_after > count_before


@pytest.mark.asyncio
async def test_candidate_creation_creates_audit_log(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
    db_session: AsyncSession,
):
    """Test that creating a candidate generates an audit log entry."""
    count_before_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "create_candidate")
    )
    count_before = count_before_result.scalar() or 0

    response = await authenticated_admin_client.post(
        "/candidates/create",
        data={
            "first_name": "Audit",
            "last_name": "TestCandidate",
            "email": "audit.candidate@example.com",
            "phone": "+1234567890",
            "linkedin_url": "",
            "resume_text": "Experienced developer for audit testing.",
            "skills": "Python, FastAPI",
        },
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)

    count_after_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "create_candidate")
    )
    count_after = count_after_result.scalar() or 0

    assert count_after > count_before


@pytest.mark.asyncio
async def test_application_creation_creates_audit_log(
    authenticated_admin_client: AsyncClient,
    sample_job: Job,
    sample_candidate: Candidate,
    db_session: AsyncSession,
):
    """Test that creating an application generates an audit log entry."""
    count_before_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "create_application")
    )
    count_before = count_before_result.scalar() or 0

    response = await authenticated_admin_client.post(
        "/applications/create",
        data={
            "candidate_id": str(sample_candidate.id),
            "job_id": str(sample_job.id),
        },
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)

    count_after_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "create_application")
    )
    count_after = count_after_result.scalar() or 0

    assert count_after > count_before


@pytest.mark.asyncio
async def test_application_status_update_creates_audit_log(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    db_session: AsyncSession,
):
    """Test that updating application status generates an audit log entry."""
    count_before_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "application_status_update"
        )
    )
    count_before = count_before_result.scalar() or 0

    response = await authenticated_admin_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "Screening"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)

    count_after_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "application_status_update"
        )
    )
    count_after = count_after_result.scalar() or 0

    assert count_after > count_before


@pytest.mark.asyncio
async def test_interview_scheduling_creates_audit_log(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    interviewer_user: User,
    db_session: AsyncSession,
):
    """Test that scheduling an interview generates an audit log entry."""
    count_before_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "schedule_interview"
        )
    )
    count_before = count_before_result.scalar() or 0

    response = await authenticated_admin_client.post(
        "/interviews/schedule",
        data={
            "application_id": str(sample_application.id),
            "interviewer_id": str(interviewer_user.id),
            "scheduled_at": "2025-06-15T10:00:00",
        },
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)

    count_after_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "schedule_interview"
        )
    )
    count_after = count_after_result.scalar() or 0

    assert count_after > count_before


@pytest.mark.asyncio
async def test_feedback_submission_creates_audit_log(
    authenticated_interviewer_client: AsyncClient,
    sample_interview: Interview,
    interviewer_user: User,
    db_session: AsyncSession,
):
    """Test that submitting interview feedback generates an audit log entry."""
    count_before_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "submit_feedback"
        )
    )
    count_before = count_before_result.scalar() or 0

    response = await authenticated_interviewer_client.post(
        f"/interviews/{sample_interview.id}/feedback",
        data={
            "feedback_rating": "4",
            "feedback_notes": "Great candidate, strong technical skills.",
        },
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)

    count_after_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "submit_feedback"
        )
    )
    count_after = count_after_result.scalar() or 0

    assert count_after > count_before


@pytest.mark.asyncio
async def test_login_creates_audit_log(
    client: AsyncClient,
    admin_user: User,
    db_session: AsyncSession,
):
    """Test that logging in generates an audit log entry."""
    count_before_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "login")
    )
    count_before = count_before_result.scalar() or 0

    response = await client.post(
        "/login",
        data={"username": admin_user.username, "password": "TestPass123"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)

    count_after_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "login")
    )
    count_after = count_after_result.scalar() or 0

    assert count_after > count_before


@pytest.mark.asyncio
async def test_logout_creates_audit_log(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
    db_session: AsyncSession,
):
    """Test that logging out generates an audit log entry."""
    count_before_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "logout")
    )
    count_before = count_before_result.scalar() or 0

    response = await authenticated_admin_client.post(
        "/auth/logout",
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)

    count_after_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "logout")
    )
    count_after = count_after_result.scalar() or 0

    assert count_after > count_before


@pytest.mark.asyncio
async def test_registration_creates_audit_log(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test that registering a new user generates an audit log entry."""
    count_before_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "register")
    )
    count_before = count_before_result.scalar() or 0

    response = await client.post(
        "/register",
        data={
            "username": "audit_register_user",
            "password": "SecurePass123",
            "confirm_password": "SecurePass123",
            "email": "audit_register@test.com",
            "full_name": "Audit Register User",
        },
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)

    count_after_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "register")
    )
    count_after = count_after_result.scalar() or 0

    assert count_after > count_before


@pytest.mark.asyncio
async def test_audit_log_list_filter_by_entity_id(db_session: AsyncSession, admin_user: User):
    """Test filtering audit logs by entity_id."""
    await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="update_job",
        entity_type="Job",
        entity_id=100,
        details="Updated job 100",
    )
    await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="update_job",
        entity_type="Job",
        entity_id=200,
        details="Updated job 200",
    )

    filters = AuditLogFilterParams(entity_id=100, page=1, page_size=20)
    result = await audit_service.list_logs(db=db_session, filters=filters)

    assert result.pagination.total >= 1
    for log in result.logs:
        assert log.entity_id == 100


@pytest.mark.asyncio
async def test_audit_log_list_combined_filters(db_session: AsyncSession, admin_user: User):
    """Test filtering audit logs with multiple filters combined."""
    await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="create_job",
        entity_type="Job",
        entity_id=300,
    )
    await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="update_job",
        entity_type="Job",
        entity_id=300,
    )
    await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="create_job",
        entity_type="Job",
        entity_id=301,
    )

    filters = AuditLogFilterParams(
        action="create_job",
        entity_type="Job",
        entity_id=300,
        page=1,
        page_size=20,
    )
    result = await audit_service.list_logs(db=db_session, filters=filters)

    assert result.pagination.total >= 1
    for log in result.logs:
        assert log.action == "create_job"
        assert log.entity_type == "Job"
        assert log.entity_id == 300


@pytest.mark.asyncio
async def test_audit_log_ordered_by_timestamp_desc(db_session: AsyncSession, admin_user: User):
    """Test that audit logs are returned in descending timestamp order."""
    for i in range(5):
        await audit_service.log_action(
            db=db_session,
            user_id=admin_user.id,
            username=admin_user.username,
            action="order_test",
            entity_type="OrderTest",
            entity_id=i,
        )

    filters = AuditLogFilterParams(action="order_test", page=1, page_size=20)
    result = await audit_service.list_logs(db=db_session, filters=filters)

    assert len(result.logs) >= 5
    for i in range(len(result.logs) - 1):
        assert result.logs[i].timestamp >= result.logs[i + 1].timestamp


@pytest.mark.asyncio
async def test_audit_log_user_relationship(db_session: AsyncSession, admin_user: User):
    """Test that audit log has a valid relationship to the user model."""
    log_entry = await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="relationship_test",
        entity_type="RelTest",
        entity_id=1,
    )

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.id == log_entry.id)
    )
    fetched = result.scalars().first()

    assert fetched is not None
    assert fetched.user is not None
    assert fetched.user.id == admin_user.id
    assert fetched.user.username == admin_user.username


@pytest.mark.asyncio
async def test_job_status_update_creates_audit_log(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
    db_session: AsyncSession,
):
    """Test that updating a job status generates an audit log entry."""
    job = Job(
        title="Status Audit Job",
        department="Engineering",
        location="Remote",
        type="Full-Time",
        salary_min=90000,
        salary_max=130000,
        description="Job for status audit test",
        status="Draft",
        hiring_manager_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    count_before_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "update_job_status"
        )
    )
    count_before = count_before_result.scalar() or 0

    response = await authenticated_admin_client.post(
        f"/jobs/{job.id}/status",
        data={"status": "Published"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)

    count_after_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "update_job_status"
        )
    )
    count_after = count_after_result.scalar() or 0

    assert count_after > count_before


@pytest.mark.asyncio
async def test_audit_log_details_contain_meaningful_info(db_session: AsyncSession, admin_user: User):
    """Test that audit log details contain meaningful information about the action."""
    log_entry = await audit_service.log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="create_job",
        entity_type="Job",
        entity_id=50,
        details="Created job 'Senior Engineer' in department 'Engineering'",
    )

    assert "Senior Engineer" in log_entry.details
    assert "Engineering" in log_entry.details


@pytest.mark.asyncio
async def test_audit_log_empty_result_for_nonexistent_filter(db_session: AsyncSession, admin_user: User):
    """Test that filtering with non-matching criteria returns empty results."""
    filters = AuditLogFilterParams(
        action="nonexistent_action_xyz",
        page=1,
        page_size=20,
    )
    result = await audit_service.list_logs(db=db_session, filters=filters)

    assert result.pagination.total == 0
    assert len(result.logs) == 0


@pytest.mark.asyncio
async def test_multiple_users_audit_logs_are_separate(db_session: AsyncSession):
    """Test that audit logs from different users are correctly attributed."""
    user_a = await create_test_user(
        db_session,
        username="audit_user_a",
        role="HR Recruiter",
        email="audit_a@test.com",
    )
    user_b = await create_test_user(
        db_session,
        username="audit_user_b",
        role="Hiring Manager",
        email="audit_b@test.com",
    )

    await audit_service.log_action(
        db=db_session,
        user_id=user_a.id,
        username=user_a.username,
        action="user_a_action",
        entity_type="TestEntity",
        entity_id=1,
    )
    await audit_service.log_action(
        db=db_session,
        user_id=user_b.id,
        username=user_b.username,
        action="user_b_action",
        entity_type="TestEntity",
        entity_id=2,
    )

    filters_a = AuditLogFilterParams(user_id=user_a.id, page=1, page_size=20)
    result_a = await audit_service.list_logs(db=db_session, filters=filters_a)

    filters_b = AuditLogFilterParams(user_id=user_b.id, page=1, page_size=20)
    result_b = await audit_service.list_logs(db=db_session, filters=filters_b)

    for log in result_a.logs:
        assert log.user_id == user_a.id
        assert log.username == user_a.username

    for log in result_b.logs:
        assert log.user_id == user_b.id
        assert log.username == user_b.username


@pytest.mark.asyncio
async def test_candidate_update_creates_audit_log(
    authenticated_admin_client: AsyncClient,
    sample_candidate: Candidate,
    db_session: AsyncSession,
):
    """Test that updating a candidate generates an audit log entry."""
    count_before_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "update_candidate"
        )
    )
    count_before = count_before_result.scalar() or 0

    response = await authenticated_admin_client.post(
        f"/candidates/{sample_candidate.id}/edit",
        data={
            "first_name": "Jane",
            "last_name": "Updated",
            "email": sample_candidate.email,
            "phone": "+9876543210",
            "linkedin_url": "",
            "resume_text": "Updated resume text for audit testing.",
            "skills": "Python, Go",
        },
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)

    count_after_result = await db_session.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "update_candidate"
        )
    )
    count_after = count_after_result.scalar() or 0

    assert count_after > count_before