import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.job import Job
from app.models.user import User
from tests.conftest import create_test_user, login_user


@pytest.mark.asyncio
async def test_create_application_as_admin(
    authenticated_admin_client: AsyncClient,
    sample_job: Job,
    sample_candidate: Candidate,
):
    response = await authenticated_admin_client.post(
        "/applications/create",
        data={
            "candidate_id": sample_candidate.id,
            "job_id": sample_job.id,
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert "/applications/" in location


@pytest.mark.asyncio
async def test_create_application_as_hr(
    authenticated_hr_client: AsyncClient,
    sample_job: Job,
    sample_candidate: Candidate,
):
    response = await authenticated_hr_client.post(
        "/applications/create",
        data={
            "candidate_id": sample_candidate.id,
            "job_id": sample_job.id,
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert "/applications/" in location


@pytest.mark.asyncio
async def test_create_application_interviewer_redirected(
    authenticated_interviewer_client: AsyncClient,
    sample_job: Job,
    sample_candidate: Candidate,
):
    response = await authenticated_interviewer_client.post(
        "/applications/create",
        data={
            "candidate_id": sample_candidate.id,
            "job_id": sample_job.id,
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert location == "/applications/"


@pytest.mark.asyncio
async def test_create_application_duplicate_returns_error(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    sample_job: Job,
    sample_candidate: Candidate,
):
    response = await authenticated_admin_client.post(
        "/applications/create",
        data={
            "candidate_id": sample_candidate.id,
            "job_id": sample_job.id,
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_application_invalid_candidate(
    authenticated_admin_client: AsyncClient,
    sample_job: Job,
):
    response = await authenticated_admin_client.post(
        "/applications/create",
        data={
            "candidate_id": 99999,
            "job_id": sample_job.id,
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_application_invalid_job(
    authenticated_admin_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_admin_client.post(
        "/applications/create",
        data={
            "candidate_id": sample_candidate.id,
            "job_id": 99999,
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_applications_authenticated(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
):
    response = await authenticated_admin_client.get("/applications/")
    assert response.status_code == 200
    assert "Applications" in response.text


@pytest.mark.asyncio
async def test_list_applications_unauthenticated(
    client: AsyncClient,
):
    response = await client.get("/applications/", follow_redirects=False)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_applications_filter_by_status(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
):
    response = await authenticated_admin_client.get("/applications/?status=Applied")
    assert response.status_code == 200
    assert "Applied" in response.text


@pytest.mark.asyncio
async def test_list_applications_filter_by_job(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    sample_job: Job,
):
    response = await authenticated_admin_client.get(
        f"/applications/?job_id={sample_job.id}"
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_application_detail_found(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
):
    response = await authenticated_admin_client.get(
        f"/applications/{sample_application.id}"
    )
    assert response.status_code == 200
    assert f"Application #{sample_application.id}" in response.text


@pytest.mark.asyncio
async def test_application_detail_not_found(
    authenticated_admin_client: AsyncClient,
):
    response = await authenticated_admin_client.get("/applications/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_application_detail_shows_interviews(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    sample_interview: Interview,
):
    response = await authenticated_admin_client.get(
        f"/applications/{sample_application.id}"
    )
    assert response.status_code == 200
    assert "Interviews" in response.text


@pytest.mark.asyncio
async def test_status_transition_applied_to_screening(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
):
    assert sample_application.status == "Applied"

    response = await authenticated_admin_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "Screening"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert f"/applications/{sample_application.id}" in location


@pytest.mark.asyncio
async def test_status_transition_screening_to_interview(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    db_session: AsyncSession,
):
    sample_application.status = "Screening"
    await db_session.flush()

    response = await authenticated_admin_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "Interview"},
        follow_redirects=False,
    )
    assert response.status_code == 302


@pytest.mark.asyncio
async def test_status_transition_screening_to_rejected(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    db_session: AsyncSession,
):
    sample_application.status = "Screening"
    await db_session.flush()

    response = await authenticated_admin_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "Rejected"},
        follow_redirects=False,
    )
    assert response.status_code == 302


@pytest.mark.asyncio
async def test_status_transition_interview_to_offer(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    db_session: AsyncSession,
):
    sample_application.status = "Interview"
    await db_session.flush()

    response = await authenticated_admin_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "Offer"},
        follow_redirects=False,
    )
    assert response.status_code == 302


@pytest.mark.asyncio
async def test_status_transition_offer_to_hired(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    db_session: AsyncSession,
):
    sample_application.status = "Offer"
    await db_session.flush()

    response = await authenticated_admin_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "Hired"},
        follow_redirects=False,
    )
    assert response.status_code == 302


@pytest.mark.asyncio
async def test_status_transition_invalid_applied_to_hired(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
):
    assert sample_application.status == "Applied"

    response = await authenticated_admin_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "Hired"},
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_status_transition_invalid_applied_to_offer(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
):
    assert sample_application.status == "Applied"

    response = await authenticated_admin_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "Offer"},
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_status_transition_invalid_applied_to_interview(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
):
    assert sample_application.status == "Applied"

    response = await authenticated_admin_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "Interview"},
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_status_transition_invalid_hired_to_anything(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    db_session: AsyncSession,
):
    sample_application.status = "Hired"
    await db_session.flush()

    response = await authenticated_admin_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "Rejected"},
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_status_transition_invalid_rejected_to_anything(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    db_session: AsyncSession,
):
    sample_application.status = "Rejected"
    await db_session.flush()

    response = await authenticated_admin_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "Applied"},
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_status_transition_invalid_status_value(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
):
    response = await authenticated_admin_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "InvalidStatus"},
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_status_transition_nonexistent_application(
    authenticated_admin_client: AsyncClient,
):
    response = await authenticated_admin_client.post(
        "/applications/99999/status",
        data={"status": "Screening"},
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_status_update_interviewer_not_allowed(
    authenticated_interviewer_client: AsyncClient,
    sample_application: Application,
):
    response = await authenticated_interviewer_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "Screening"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert f"/applications/{sample_application.id}" in location


@pytest.mark.asyncio
async def test_status_update_hiring_manager_allowed(
    authenticated_manager_client: AsyncClient,
    sample_application: Application,
):
    response = await authenticated_manager_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "Screening"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert f"/applications/{sample_application.id}" in location


@pytest.mark.asyncio
async def test_pipeline_view_authenticated(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
):
    response = await authenticated_admin_client.get("/applications/pipeline")
    assert response.status_code == 200
    assert "Application Pipeline" in response.text


@pytest.mark.asyncio
async def test_pipeline_view_shows_all_stages(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
):
    response = await authenticated_admin_client.get("/applications/pipeline")
    assert response.status_code == 200
    for stage in ["Applied", "Screening", "Interview", "Offer", "Hired", "Rejected"]:
        assert stage in response.text


@pytest.mark.asyncio
async def test_pipeline_view_filter_by_job(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    sample_job: Job,
):
    response = await authenticated_admin_client.get(
        f"/applications/pipeline?job_id={sample_job.id}"
    )
    assert response.status_code == 200
    assert sample_job.title in response.text


@pytest.mark.asyncio
async def test_pipeline_view_unauthenticated(
    client: AsyncClient,
):
    response = await client.get("/applications/pipeline", follow_redirects=False)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_application_form_get_as_admin(
    authenticated_admin_client: AsyncClient,
):
    response = await authenticated_admin_client.get("/applications/create")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_application_form_get_as_interviewer_redirected(
    authenticated_interviewer_client: AsyncClient,
):
    response = await authenticated_interviewer_client.get(
        "/applications/create",
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert location == "/applications/"


@pytest.mark.asyncio
async def test_application_detail_shows_candidate_info(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    sample_candidate: Candidate,
):
    response = await authenticated_admin_client.get(
        f"/applications/{sample_application.id}"
    )
    assert response.status_code == 200
    assert sample_candidate.name in response.text
    assert sample_candidate.email in response.text


@pytest.mark.asyncio
async def test_application_detail_shows_job_info(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    sample_job: Job,
):
    response = await authenticated_admin_client.get(
        f"/applications/{sample_application.id}"
    )
    assert response.status_code == 200
    assert sample_job.title in response.text
    assert sample_job.department in response.text


@pytest.mark.asyncio
async def test_application_detail_shows_allowed_transitions(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
):
    response = await authenticated_admin_client.get(
        f"/applications/{sample_application.id}"
    )
    assert response.status_code == 200
    assert "Move to Screening" in response.text


@pytest.mark.asyncio
async def test_application_detail_hired_no_transitions(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
    db_session: AsyncSession,
):
    sample_application.status = "Hired"
    await db_session.flush()

    response = await authenticated_admin_client.get(
        f"/applications/{sample_application.id}"
    )
    assert response.status_code == 200
    assert "Move to" not in response.text or "Update Status" not in response.text


@pytest.mark.asyncio
async def test_full_pipeline_transition_happy_path(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
):
    transitions = [
        ("Screening", 302),
        ("Interview", 302),
        ("Offer", 302),
        ("Hired", 302),
    ]

    for new_status, expected_code in transitions:
        response = await authenticated_admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": new_status},
            follow_redirects=False,
        )
        assert response.status_code == expected_code, (
            f"Failed transitioning to {new_status}: got {response.status_code}"
        )


@pytest.mark.asyncio
async def test_full_pipeline_rejection_from_interview(
    authenticated_admin_client: AsyncClient,
    sample_application: Application,
):
    await authenticated_admin_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "Screening"},
        follow_redirects=False,
    )

    await authenticated_admin_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "Interview"},
        follow_redirects=False,
    )

    response = await authenticated_admin_client.post(
        f"/applications/{sample_application.id}/status",
        data={"status": "Rejected"},
        follow_redirects=False,
    )
    assert response.status_code == 302


@pytest.mark.asyncio
async def test_list_applications_as_interviewer(
    authenticated_interviewer_client: AsyncClient,
    sample_application: Application,
):
    response = await authenticated_interviewer_client.get("/applications/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_applications_as_hiring_manager(
    authenticated_manager_client: AsyncClient,
    sample_application: Application,
):
    response = await authenticated_manager_client.get("/applications/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_pipeline_view_empty(
    authenticated_admin_client: AsyncClient,
):
    response = await authenticated_admin_client.get("/applications/pipeline")
    assert response.status_code == 200
    assert "No applications" in response.text or "Application Pipeline" in response.text