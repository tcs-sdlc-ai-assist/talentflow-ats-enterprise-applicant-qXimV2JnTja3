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

from tests.conftest import create_test_user, login_user


@pytest.mark.asyncio
async def test_schedule_interview_as_admin(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    interviewer_user: User,
):
    scheduled_time = (datetime.utcnow() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")

    response = await authenticated_admin_client.post(
        "/interviews/schedule",
        data={
            "application_id": str(sample_application.id),
            "interviewer_id": str(interviewer_user.id),
            "scheduled_at": scheduled_time,
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/interviews/" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_schedule_interview_as_hr(
    authenticated_hr_client: AsyncClient,
    sample_application: Application,
    interviewer_user: User,
):
    scheduled_time = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M")

    response = await authenticated_hr_client.post(
        "/interviews/schedule",
        data={
            "application_id": str(sample_application.id),
            "interviewer_id": str(interviewer_user.id),
            "scheduled_at": scheduled_time,
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/interviews/" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_schedule_interview_rbac_interviewer_denied(
    authenticated_interviewer_client: AsyncClient,
    sample_application: Application,
    interviewer_user: User,
):
    scheduled_time = (datetime.utcnow() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")

    response = await authenticated_interviewer_client.post(
        "/interviews/schedule",
        data={
            "application_id": str(sample_application.id),
            "interviewer_id": str(interviewer_user.id),
            "scheduled_at": scheduled_time,
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers.get("location", "") == "/interviews/"


@pytest.mark.asyncio
async def test_schedule_interview_rbac_hiring_manager_denied(
    authenticated_manager_client: AsyncClient,
    sample_application: Application,
    interviewer_user: User,
):
    scheduled_time = (datetime.utcnow() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")

    response = await authenticated_manager_client.post(
        "/interviews/schedule",
        data={
            "application_id": str(sample_application.id),
            "interviewer_id": str(interviewer_user.id),
            "scheduled_at": scheduled_time,
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers.get("location", "") == "/interviews/"


@pytest.mark.asyncio
async def test_schedule_interview_invalid_datetime(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    interviewer_user: User,
):
    response = await authenticated_admin_client.post(
        "/interviews/schedule",
        data={
            "application_id": str(sample_application.id),
            "interviewer_id": str(interviewer_user.id),
            "scheduled_at": "not-a-date",
        },
        follow_redirects=False,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_schedule_interview_invalid_application_id(
    authenticated_admin_client: AsyncClient,
    interviewer_user: User,
):
    scheduled_time = (datetime.utcnow() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")

    response = await authenticated_admin_client.post(
        "/interviews/schedule",
        data={
            "application_id": "99999",
            "interviewer_id": str(interviewer_user.id),
            "scheduled_at": scheduled_time,
        },
        follow_redirects=False,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_schedule_interview_invalid_interviewer_id(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
):
    scheduled_time = (datetime.utcnow() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")

    response = await authenticated_admin_client.post(
        "/interviews/schedule",
        data={
            "application_id": str(sample_application.id),
            "interviewer_id": "99999",
            "scheduled_at": scheduled_time,
        },
        follow_redirects=False,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_schedule_interview_form_get_as_admin(
    authenticated_admin_client: AsyncClient,
):
    response = await authenticated_admin_client.get(
        "/interviews/schedule",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert b"Schedule" in response.content or b"schedule" in response.content


@pytest.mark.asyncio
async def test_schedule_interview_form_get_denied_for_interviewer(
    authenticated_interviewer_client: AsyncClient,
):
    response = await authenticated_interviewer_client.get(
        "/interviews/schedule",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers.get("location", "") == "/interviews/"


@pytest.mark.asyncio
async def test_submit_feedback_as_interviewer(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_application: Application,
):
    interviewer = await create_test_user(
        db_session,
        username="feedback_interviewer",
        role="Interviewer",
        email="feedback_interviewer@test.com",
    )

    interview = Interview(
        application_id=sample_application.id,
        interviewer_id=interviewer.id,
        scheduled_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)

    logged_in_client = await login_user(client, interviewer.username)

    response = await logged_in_client.post(
        f"/interviews/{interview.id}/feedback",
        data={
            "feedback_rating": "4",
            "feedback_notes": "Strong technical skills, good communication.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/interviews/my" in response.headers.get("location", "")

    await db_session.refresh(interview)
    assert interview.feedback_rating == 4
    assert interview.feedback_notes == "Strong technical skills, good communication."
    assert interview.feedback_submitted_at is not None


@pytest.mark.asyncio
async def test_submit_feedback_as_admin(
    authenticated_admin_client: AsyncClient,
    sample_interview: Interview,
    db_session: AsyncSession,
):
    response = await authenticated_admin_client.post(
        f"/interviews/{sample_interview.id}/feedback",
        data={
            "feedback_rating": "5",
            "feedback_notes": "Excellent candidate, highly recommended.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    await db_session.refresh(sample_interview)
    assert sample_interview.feedback_rating == 5
    assert sample_interview.feedback_notes == "Excellent candidate, highly recommended."
    assert sample_interview.feedback_submitted_at is not None


@pytest.mark.asyncio
async def test_submit_feedback_timestamp_is_set(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_application: Application,
):
    interviewer = await create_test_user(
        db_session,
        username="ts_interviewer",
        role="Interviewer",
        email="ts_interviewer@test.com",
    )

    interview = Interview(
        application_id=sample_application.id,
        interviewer_id=interviewer.id,
        scheduled_at=datetime.utcnow() + timedelta(days=2),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)

    assert interview.feedback_submitted_at is None

    before_submit = datetime.utcnow()

    logged_in_client = await login_user(client, interviewer.username)
    response = await logged_in_client.post(
        f"/interviews/{interview.id}/feedback",
        data={
            "feedback_rating": "3",
            "feedback_notes": "Average performance overall.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    await db_session.refresh(interview)
    assert interview.feedback_submitted_at is not None
    assert interview.feedback_submitted_at >= before_submit


@pytest.mark.asyncio
async def test_submit_feedback_duplicate_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_application: Application,
):
    interviewer = await create_test_user(
        db_session,
        username="dup_feedback_interviewer",
        role="Interviewer",
        email="dup_feedback@test.com",
    )

    interview = Interview(
        application_id=sample_application.id,
        interviewer_id=interviewer.id,
        scheduled_at=datetime.utcnow() + timedelta(days=1),
        feedback_rating=4,
        feedback_notes="Already submitted.",
        feedback_submitted_at=datetime.utcnow(),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)

    logged_in_client = await login_user(client, interviewer.username)

    response = await logged_in_client.post(
        f"/interviews/{interview.id}/feedback",
        data={
            "feedback_rating": "5",
            "feedback_notes": "Trying to submit again.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_submit_feedback_invalid_rating_out_of_range(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_application: Application,
):
    interviewer = await create_test_user(
        db_session,
        username="bad_rating_interviewer",
        role="Interviewer",
        email="bad_rating@test.com",
    )

    interview = Interview(
        application_id=sample_application.id,
        interviewer_id=interviewer.id,
        scheduled_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)

    logged_in_client = await login_user(client, interviewer.username)

    response = await logged_in_client.post(
        f"/interviews/{interview.id}/feedback",
        data={
            "feedback_rating": "6",
            "feedback_notes": "Rating out of range.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_submit_feedback_empty_notes(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_application: Application,
):
    interviewer = await create_test_user(
        db_session,
        username="empty_notes_interviewer",
        role="Interviewer",
        email="empty_notes@test.com",
    )

    interview = Interview(
        application_id=sample_application.id,
        interviewer_id=interviewer.id,
        scheduled_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)

    logged_in_client = await login_user(client, interviewer.username)

    response = await logged_in_client.post(
        f"/interviews/{interview.id}/feedback",
        data={
            "feedback_rating": "3",
            "feedback_notes": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_submit_feedback_nonexistent_interview(
    authenticated_admin_client: AsyncClient,
):
    response = await authenticated_admin_client.post(
        "/interviews/99999/feedback",
        data={
            "feedback_rating": "3",
            "feedback_notes": "This interview does not exist.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_submit_feedback_rbac_wrong_interviewer_denied(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_application: Application,
):
    assigned_interviewer = await create_test_user(
        db_session,
        username="assigned_interviewer",
        role="Interviewer",
        email="assigned@test.com",
    )

    other_interviewer = await create_test_user(
        db_session,
        username="other_interviewer",
        role="Interviewer",
        email="other@test.com",
    )

    interview = Interview(
        application_id=sample_application.id,
        interviewer_id=assigned_interviewer.id,
        scheduled_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)

    logged_in_client = await login_user(client, other_interviewer.username)

    response = await logged_in_client.post(
        f"/interviews/{interview.id}/feedback",
        data={
            "feedback_rating": "4",
            "feedback_notes": "Should not be allowed.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/interviews/my" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_my_interviews_page_as_interviewer(
    authenticated_interviewer_client: AsyncClient,
    sample_interview: Interview,
):
    response = await authenticated_interviewer_client.get(
        "/interviews/my",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert b"My Interview Queue" in response.content or b"interview" in response.content.lower()


@pytest.mark.asyncio
async def test_my_interviews_shows_assigned_interviews(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_application: Application,
):
    interviewer = await create_test_user(
        db_session,
        username="my_queue_interviewer",
        role="Interviewer",
        email="my_queue@test.com",
    )

    interview = Interview(
        application_id=sample_application.id,
        interviewer_id=interviewer.id,
        scheduled_at=datetime.utcnow() + timedelta(days=2),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)

    logged_in_client = await login_user(client, interviewer.username)

    response = await logged_in_client.get(
        "/interviews/my",
        follow_redirects=False,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_my_interviews_empty_for_new_interviewer(
    client: AsyncClient,
    db_session: AsyncSession,
):
    interviewer = await create_test_user(
        db_session,
        username="new_interviewer",
        role="Interviewer",
        email="new_interviewer@test.com",
    )

    logged_in_client = await login_user(client, interviewer.username)

    response = await logged_in_client.get(
        "/interviews/my",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert b"No interviews assigned" in response.content or b"no" in response.content.lower()


@pytest.mark.asyncio
async def test_interviews_list_page_as_admin(
    authenticated_admin_client: AsyncClient,
    sample_interview: Interview,
):
    response = await authenticated_admin_client.get(
        "/interviews/",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert b"Interviews" in response.content or b"interviews" in response.content.lower()


@pytest.mark.asyncio
async def test_interviews_list_filter_by_feedback_status_pending(
    authenticated_admin_client: AsyncClient,
    sample_interview: Interview,
):
    response = await authenticated_admin_client.get(
        "/interviews/?feedback_status=pending",
        follow_redirects=False,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_interviews_list_filter_by_feedback_status_submitted(
    authenticated_admin_client: AsyncClient,
    db_session: AsyncSession,
    sample_interview: Interview,
):
    sample_interview.feedback_rating = 4
    sample_interview.feedback_notes = "Good candidate."
    sample_interview.feedback_submitted_at = datetime.utcnow()
    await db_session.flush()

    response = await authenticated_admin_client.get(
        "/interviews/?feedback_status=submitted",
        follow_redirects=False,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_interview_detail_page(
    authenticated_admin_client: AsyncClient,
    sample_interview: Interview,
):
    response = await authenticated_admin_client.get(
        f"/interviews/{sample_interview.id}",
        follow_redirects=False,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_interview_detail_nonexistent(
    authenticated_admin_client: AsyncClient,
):
    response = await authenticated_admin_client.get(
        "/interviews/99999",
        follow_redirects=False,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_feedback_form_get_as_assigned_interviewer(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_application: Application,
):
    interviewer = await create_test_user(
        db_session,
        username="form_interviewer",
        role="Interviewer",
        email="form_interviewer@test.com",
    )

    interview = Interview(
        application_id=sample_application.id,
        interviewer_id=interviewer.id,
        scheduled_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)

    logged_in_client = await login_user(client, interviewer.username)

    response = await logged_in_client.get(
        f"/interviews/{interview.id}/feedback",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert b"Feedback" in response.content or b"feedback" in response.content.lower()


@pytest.mark.asyncio
async def test_feedback_form_get_denied_for_wrong_interviewer(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_application: Application,
):
    assigned = await create_test_user(
        db_session,
        username="assigned_for_form",
        role="Interviewer",
        email="assigned_form@test.com",
    )

    wrong = await create_test_user(
        db_session,
        username="wrong_for_form",
        role="Interviewer",
        email="wrong_form@test.com",
    )

    interview = Interview(
        application_id=sample_application.id,
        interviewer_id=assigned.id,
        scheduled_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)

    logged_in_client = await login_user(client, wrong.username)

    response = await logged_in_client.get(
        f"/interviews/{interview.id}/feedback",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/interviews/my" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_unauthenticated_user_cannot_access_interviews(
    client: AsyncClient,
):
    response = await client.get(
        "/interviews/",
        follow_redirects=False,
    )

    assert response.status_code == 401 or response.status_code == 302


@pytest.mark.asyncio
async def test_unauthenticated_user_cannot_access_my_interviews(
    client: AsyncClient,
):
    response = await client.get(
        "/interviews/my",
        follow_redirects=False,
    )

    assert response.status_code == 401 or response.status_code == 302


@pytest.mark.asyncio
async def test_unauthenticated_user_cannot_submit_feedback(
    client: AsyncClient,
    sample_interview: Interview,
):
    response = await client.post(
        f"/interviews/{sample_interview.id}/feedback",
        data={
            "feedback_rating": "4",
            "feedback_notes": "Should not work.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 401 or response.status_code == 302


@pytest.mark.asyncio
async def test_feedback_rating_boundary_value_1(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_application: Application,
):
    interviewer = await create_test_user(
        db_session,
        username="boundary_1_interviewer",
        role="Interviewer",
        email="boundary1@test.com",
    )

    interview = Interview(
        application_id=sample_application.id,
        interviewer_id=interviewer.id,
        scheduled_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)

    logged_in_client = await login_user(client, interviewer.username)

    response = await logged_in_client.post(
        f"/interviews/{interview.id}/feedback",
        data={
            "feedback_rating": "1",
            "feedback_notes": "Minimum rating test.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    await db_session.refresh(interview)
    assert interview.feedback_rating == 1


@pytest.mark.asyncio
async def test_feedback_rating_boundary_value_5(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_application: Application,
):
    interviewer = await create_test_user(
        db_session,
        username="boundary_5_interviewer",
        role="Interviewer",
        email="boundary5@test.com",
    )

    interview = Interview(
        application_id=sample_application.id,
        interviewer_id=interviewer.id,
        scheduled_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)

    logged_in_client = await login_user(client, interviewer.username)

    response = await logged_in_client.post(
        f"/interviews/{interview.id}/feedback",
        data={
            "feedback_rating": "5",
            "feedback_notes": "Maximum rating test.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    await db_session.refresh(interview)
    assert interview.feedback_rating == 5


@pytest.mark.asyncio
async def test_feedback_rating_zero_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_application: Application,
):
    interviewer = await create_test_user(
        db_session,
        username="zero_rating_interviewer",
        role="Interviewer",
        email="zero_rating@test.com",
    )

    interview = Interview(
        application_id=sample_application.id,
        interviewer_id=interviewer.id,
        scheduled_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)

    logged_in_client = await login_user(client, interviewer.username)

    response = await logged_in_client.post(
        f"/interviews/{interview.id}/feedback",
        data={
            "feedback_rating": "0",
            "feedback_notes": "Zero rating should be rejected.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 400