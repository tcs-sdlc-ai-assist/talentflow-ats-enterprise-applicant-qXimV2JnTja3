import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.user import User
from tests.conftest import create_test_user, login_user


@pytest.mark.asyncio
async def test_create_job_as_admin(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
):
    response = await authenticated_admin_client.post(
        "/jobs/",
        data={
            "title": "Backend Engineer",
            "department": "Engineering",
            "location": "Remote",
            "type": "Full-Time",
            "salary_min": "90000",
            "salary_max": "120000",
            "description": "Build scalable APIs with Python and FastAPI.",
            "hiring_manager_id": str(admin_user.id),
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert "/jobs/" in location


@pytest.mark.asyncio
async def test_create_job_as_hr(
    authenticated_hr_client: AsyncClient,
    hr_user: User,
):
    response = await authenticated_hr_client.post(
        "/jobs/",
        data={
            "title": "Frontend Developer",
            "department": "Engineering",
            "location": "New York",
            "type": "Full-Time",
            "salary_min": "80000",
            "salary_max": "110000",
            "description": "Build beautiful UIs with React.",
            "hiring_manager_id": str(hr_user.id),
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert "/jobs/" in location


@pytest.mark.asyncio
async def test_create_job_as_interviewer_redirects(
    authenticated_interviewer_client: AsyncClient,
    interviewer_user: User,
):
    response = await authenticated_interviewer_client.post(
        "/jobs/",
        data={
            "title": "Should Not Be Created",
            "department": "Engineering",
            "location": "Remote",
            "type": "Full-Time",
            "salary_min": "50000",
            "salary_max": "70000",
            "description": "This job should not be created by an interviewer.",
            "hiring_manager_id": str(interviewer_user.id),
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert location == "/jobs/"


@pytest.mark.asyncio
async def test_create_job_form_accessible_by_admin(
    authenticated_admin_client: AsyncClient,
):
    response = await authenticated_admin_client.get(
        "/jobs/create",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Create" in response.content or b"create" in response.content


@pytest.mark.asyncio
async def test_create_job_form_redirects_for_interviewer(
    authenticated_interviewer_client: AsyncClient,
):
    response = await authenticated_interviewer_client.get(
        "/jobs/create",
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert location == "/jobs/"


@pytest.mark.asyncio
async def test_list_jobs_page(
    authenticated_admin_client: AsyncClient,
    sample_job: Job,
):
    response = await authenticated_admin_client.get(
        "/jobs/",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Senior Python Developer" in response.content


@pytest.mark.asyncio
async def test_list_jobs_filter_by_status(
    authenticated_admin_client: AsyncClient,
    sample_job: Job,
):
    response = await authenticated_admin_client.get(
        "/jobs/?status=Published",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Senior Python Developer" in response.content

    response_draft = await authenticated_admin_client.get(
        "/jobs/?status=Draft",
        follow_redirects=False,
    )
    assert response_draft.status_code == 200
    assert b"Senior Python Developer" not in response_draft.content


@pytest.mark.asyncio
async def test_list_jobs_filter_by_department(
    authenticated_admin_client: AsyncClient,
    sample_job: Job,
):
    response = await authenticated_admin_client.get(
        "/jobs/?department=Engineering",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Senior Python Developer" in response.content

    response_other = await authenticated_admin_client.get(
        "/jobs/?department=Marketing",
        follow_redirects=False,
    )
    assert response_other.status_code == 200
    assert b"Senior Python Developer" not in response_other.content


@pytest.mark.asyncio
async def test_list_jobs_search(
    authenticated_admin_client: AsyncClient,
    sample_job: Job,
):
    response = await authenticated_admin_client.get(
        "/jobs/?search=Python",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Senior Python Developer" in response.content

    response_no_match = await authenticated_admin_client.get(
        "/jobs/?search=Nonexistent",
        follow_redirects=False,
    )
    assert response_no_match.status_code == 200
    assert b"Senior Python Developer" not in response_no_match.content


@pytest.mark.asyncio
async def test_job_detail_page(
    authenticated_admin_client: AsyncClient,
    sample_job: Job,
):
    response = await authenticated_admin_client.get(
        f"/jobs/{sample_job.id}",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Senior Python Developer" in response.content
    assert b"Engineering" in response.content
    assert b"Remote" in response.content


@pytest.mark.asyncio
async def test_job_detail_nonexistent_redirects(
    authenticated_admin_client: AsyncClient,
):
    response = await authenticated_admin_client.get(
        "/jobs/99999",
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert location == "/jobs/"


@pytest.mark.asyncio
async def test_edit_job_form_accessible_by_admin(
    authenticated_admin_client: AsyncClient,
    sample_job: Job,
):
    response = await authenticated_admin_client.get(
        f"/jobs/{sample_job.id}/edit",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Senior Python Developer" in response.content


@pytest.mark.asyncio
async def test_edit_job_form_accessible_by_hiring_manager(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_job: Job,
):
    manager = await create_test_user(
        db_session,
        username="job_manager",
        role="Hiring Manager",
        email="job_manager@test.com",
    )
    sample_job.hiring_manager_id = manager.id
    await db_session.flush()
    await db_session.refresh(sample_job)

    logged_in_client = await login_user(client, "job_manager")

    response = await logged_in_client.get(
        f"/jobs/{sample_job.id}/edit",
        follow_redirects=False,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_edit_job_form_redirects_for_non_owner_manager(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_job: Job,
):
    other_manager = await create_test_user(
        db_session,
        username="other_manager",
        role="Hiring Manager",
        email="other_manager@test.com",
    )

    logged_in_client = await login_user(client, "other_manager")

    response = await logged_in_client.get(
        f"/jobs/{sample_job.id}/edit",
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert f"/jobs/{sample_job.id}" in location


@pytest.mark.asyncio
async def test_edit_job_form_redirects_for_interviewer(
    authenticated_interviewer_client: AsyncClient,
    sample_job: Job,
):
    response = await authenticated_interviewer_client.get(
        f"/jobs/{sample_job.id}/edit",
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert f"/jobs/{sample_job.id}" in location


@pytest.mark.asyncio
async def test_update_job_as_admin(
    authenticated_admin_client: AsyncClient,
    sample_job: Job,
    admin_user: User,
):
    response = await authenticated_admin_client.post(
        f"/jobs/{sample_job.id}",
        data={
            "title": "Updated Python Developer",
            "department": "Engineering",
            "location": "San Francisco",
            "type": "Full-Time",
            "salary_min": "110000",
            "salary_max": "160000",
            "description": "Updated description for the role.",
            "hiring_manager_id": str(admin_user.id),
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert f"/jobs/{sample_job.id}" in location

    detail_response = await authenticated_admin_client.get(
        f"/jobs/{sample_job.id}",
        follow_redirects=False,
    )
    assert detail_response.status_code == 200
    assert b"Updated Python Developer" in detail_response.content
    assert b"San Francisco" in detail_response.content


@pytest.mark.asyncio
async def test_update_job_as_interviewer_redirects(
    authenticated_interviewer_client: AsyncClient,
    sample_job: Job,
    interviewer_user: User,
):
    response = await authenticated_interviewer_client.post(
        f"/jobs/{sample_job.id}",
        data={
            "title": "Should Not Update",
            "department": "Engineering",
            "location": "Remote",
            "type": "Full-Time",
            "salary_min": "50000",
            "salary_max": "70000",
            "description": "This should not work.",
            "hiring_manager_id": str(interviewer_user.id),
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert f"/jobs/{sample_job.id}" in location


@pytest.mark.asyncio
async def test_job_status_transition_draft_to_published(
    authenticated_admin_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="Draft Job",
        department="Sales",
        location="Chicago",
        type="Full-Time",
        salary_min=60000,
        salary_max=80000,
        description="A draft job posting.",
        status="Draft",
        hiring_manager_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await authenticated_admin_client.post(
        f"/jobs/{job.id}/status",
        data={"status": "Published"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    detail_response = await authenticated_admin_client.get(
        f"/jobs/{job.id}",
        follow_redirects=False,
    )
    assert detail_response.status_code == 200
    assert b"Published" in detail_response.content


@pytest.mark.asyncio
async def test_job_status_transition_published_to_closed(
    authenticated_admin_client: AsyncClient,
    sample_job: Job,
):
    assert sample_job.status == "Published"

    response = await authenticated_admin_client.post(
        f"/jobs/{sample_job.id}/status",
        data={"status": "Closed"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    detail_response = await authenticated_admin_client.get(
        f"/jobs/{sample_job.id}",
        follow_redirects=False,
    )
    assert detail_response.status_code == 200
    assert b"Closed" in detail_response.content


@pytest.mark.asyncio
async def test_job_status_transition_draft_to_closed(
    authenticated_admin_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="Draft to Close Job",
        department="HR",
        location="Remote",
        type="Part-Time",
        salary_min=40000,
        salary_max=55000,
        description="A job that goes from draft to closed.",
        status="Draft",
        hiring_manager_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await authenticated_admin_client.post(
        f"/jobs/{job.id}/status",
        data={"status": "Closed"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    detail_response = await authenticated_admin_client.get(
        f"/jobs/{job.id}",
        follow_redirects=False,
    )
    assert detail_response.status_code == 200
    assert b"Closed" in detail_response.content


@pytest.mark.asyncio
async def test_job_status_invalid_transition_closed_to_published(
    authenticated_admin_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="Closed Job",
        department="Engineering",
        location="Remote",
        type="Full-Time",
        salary_min=70000,
        salary_max=100000,
        description="A closed job.",
        status="Closed",
        hiring_manager_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await authenticated_admin_client.post(
        f"/jobs/{job.id}/status",
        data={"status": "Published"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    detail_response = await authenticated_admin_client.get(
        f"/jobs/{job.id}",
        follow_redirects=False,
    )
    assert detail_response.status_code == 200
    assert b"Closed" in detail_response.content


@pytest.mark.asyncio
async def test_job_status_invalid_transition_published_to_draft(
    authenticated_admin_client: AsyncClient,
    sample_job: Job,
):
    assert sample_job.status == "Published"

    response = await authenticated_admin_client.post(
        f"/jobs/{sample_job.id}/status",
        data={"status": "Draft"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    detail_response = await authenticated_admin_client.get(
        f"/jobs/{sample_job.id}",
        follow_redirects=False,
    )
    assert detail_response.status_code == 200
    assert b"Published" in detail_response.content


@pytest.mark.asyncio
async def test_job_status_update_by_interviewer_redirects(
    authenticated_interviewer_client: AsyncClient,
    sample_job: Job,
):
    response = await authenticated_interviewer_client.post(
        f"/jobs/{sample_job.id}/status",
        data={"status": "Closed"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert f"/jobs/{sample_job.id}" in location


@pytest.mark.asyncio
async def test_job_status_update_by_hiring_manager_owner(
    client: AsyncClient,
    db_session: AsyncSession,
):
    manager = await create_test_user(
        db_session,
        username="status_manager",
        role="Hiring Manager",
        email="status_manager@test.com",
    )

    job = Job(
        title="Manager Owned Job",
        department="Product",
        location="Remote",
        type="Full-Time",
        salary_min=80000,
        salary_max=120000,
        description="A job owned by a hiring manager.",
        status="Draft",
        hiring_manager_id=manager.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    logged_in_client = await login_user(client, "status_manager")

    response = await logged_in_client.post(
        f"/jobs/{job.id}/status",
        data={"status": "Published"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    detail_response = await logged_in_client.get(
        f"/jobs/{job.id}",
        follow_redirects=False,
    )
    assert detail_response.status_code == 200
    assert b"Published" in detail_response.content


@pytest.mark.asyncio
async def test_published_jobs_on_landing_page(
    client: AsyncClient,
    sample_job: Job,
):
    response = await client.get(
        "/",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Senior Python Developer" in response.content


@pytest.mark.asyncio
async def test_draft_jobs_not_on_landing_page(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    draft_job = Job(
        title="Secret Draft Job",
        department="Engineering",
        location="Remote",
        type="Full-Time",
        salary_min=50000,
        salary_max=70000,
        description="This draft job should not appear on the landing page.",
        status="Draft",
        hiring_manager_id=admin_user.id,
    )
    db_session.add(draft_job)
    await db_session.flush()

    response = await client.get(
        "/",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Secret Draft Job" not in response.content


@pytest.mark.asyncio
async def test_create_job_with_invalid_salary_range(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
):
    response = await authenticated_admin_client.post(
        "/jobs/",
        data={
            "title": "Invalid Salary Job",
            "department": "Engineering",
            "location": "Remote",
            "type": "Full-Time",
            "salary_min": "150000",
            "salary_max": "100000",
            "description": "Salary min is greater than max.",
            "hiring_manager_id": str(admin_user.id),
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_job_with_invalid_hiring_manager(
    authenticated_admin_client: AsyncClient,
):
    response = await authenticated_admin_client.post(
        "/jobs/",
        data={
            "title": "No Manager Job",
            "department": "Engineering",
            "location": "Remote",
            "type": "Full-Time",
            "salary_min": "50000",
            "salary_max": "70000",
            "description": "Hiring manager does not exist.",
            "hiring_manager_id": "99999",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_jobs_requires_authentication(
    client: AsyncClient,
):
    response = await client.get(
        "/jobs/",
        follow_redirects=False,
    )
    assert response.status_code == 401 or response.status_code == 302


@pytest.mark.asyncio
async def test_update_job_nonexistent_redirects(
    authenticated_admin_client: AsyncClient,
    admin_user: User,
):
    response = await authenticated_admin_client.post(
        "/jobs/99999",
        data={
            "title": "Ghost Job",
            "department": "Engineering",
            "location": "Remote",
            "type": "Full-Time",
            "salary_min": "50000",
            "salary_max": "70000",
            "description": "This job does not exist.",
            "hiring_manager_id": str(admin_user.id),
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert location == "/jobs/"


@pytest.mark.asyncio
async def test_job_status_update_nonexistent_redirects(
    authenticated_admin_client: AsyncClient,
):
    response = await authenticated_admin_client.post(
        "/jobs/99999/status",
        data={"status": "Published"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert location == "/jobs/"


@pytest.mark.asyncio
async def test_list_jobs_empty_state(
    client: AsyncClient,
    db_session: AsyncSession,
):
    user = await create_test_user(
        db_session,
        username="empty_list_user",
        role="System Admin",
        email="empty_list@test.com",
    )
    logged_in_client = await login_user(client, "empty_list_user")

    response = await logged_in_client.get(
        "/jobs/",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"No jobs found" in response.content


@pytest.mark.asyncio
async def test_update_job_with_status_change_in_form(
    authenticated_admin_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="Form Status Change Job",
        department="Marketing",
        location="Boston",
        type="Contract",
        salary_min=50000,
        salary_max=75000,
        description="Testing status change via edit form.",
        status="Draft",
        hiring_manager_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await authenticated_admin_client.post(
        f"/jobs/{job.id}",
        data={
            "title": "Form Status Change Job Updated",
            "department": "Marketing",
            "location": "Boston",
            "type": "Contract",
            "salary_min": "50000",
            "salary_max": "75000",
            "description": "Updated description.",
            "hiring_manager_id": str(admin_user.id),
            "status": "Published",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    detail_response = await authenticated_admin_client.get(
        f"/jobs/{job.id}",
        follow_redirects=False,
    )
    assert detail_response.status_code == 200
    assert b"Published" in detail_response.content
    assert b"Form Status Change Job Updated" in detail_response.content