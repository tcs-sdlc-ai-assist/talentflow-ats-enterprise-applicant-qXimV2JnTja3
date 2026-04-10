import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate, Skill
from app.models.user import User
from app.models.application import Application
from app.models.job import Job
from tests.conftest import create_test_user, login_user


@pytest.mark.asyncio
async def test_candidates_list_requires_login(client: AsyncClient):
    response = await client.get("/candidates/", follow_redirects=False)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_candidates_list_empty(authenticated_hr_client: AsyncClient):
    response = await authenticated_hr_client.get("/candidates/", follow_redirects=False)
    assert response.status_code == 200
    assert b"No candidates found" in response.content


@pytest.mark.asyncio
async def test_candidates_list_with_candidates(
    authenticated_hr_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_hr_client.get("/candidates/", follow_redirects=False)
    assert response.status_code == 200
    assert sample_candidate.name.encode() in response.content
    assert sample_candidate.email.encode() in response.content


@pytest.mark.asyncio
async def test_candidates_list_search_by_name(
    authenticated_hr_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_hr_client.get(
        "/candidates/?search=Jane", follow_redirects=False
    )
    assert response.status_code == 200
    assert sample_candidate.name.encode() in response.content


@pytest.mark.asyncio
async def test_candidates_list_search_by_email(
    authenticated_hr_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_hr_client.get(
        "/candidates/?search=jane.doe", follow_redirects=False
    )
    assert response.status_code == 200
    assert sample_candidate.name.encode() in response.content


@pytest.mark.asyncio
async def test_candidates_list_search_no_results(
    authenticated_hr_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_hr_client.get(
        "/candidates/?search=nonexistent_person_xyz", follow_redirects=False
    )
    assert response.status_code == 200
    assert sample_candidate.name.encode() not in response.content


@pytest.mark.asyncio
async def test_candidates_list_filter_by_skill(
    authenticated_hr_client: AsyncClient,
    db_session: AsyncSession,
    sample_candidate: Candidate,
):
    skill = Skill(name="Python")
    db_session.add(skill)
    await db_session.flush()
    await db_session.refresh(skill)

    sample_candidate.skills.append(skill)
    await db_session.flush()

    response = await authenticated_hr_client.get(
        f"/candidates/?skill={skill.id}", follow_redirects=False
    )
    assert response.status_code == 200
    assert sample_candidate.name.encode() in response.content


@pytest.mark.asyncio
async def test_create_candidate_form_requires_login(client: AsyncClient):
    response = await client.get("/candidates/create", follow_redirects=False)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_candidate_form_hr_access(authenticated_hr_client: AsyncClient):
    response = await authenticated_hr_client.get(
        "/candidates/create", follow_redirects=False
    )
    assert response.status_code == 200
    assert b"Add New Candidate" in response.content


@pytest.mark.asyncio
async def test_create_candidate_form_admin_access(authenticated_admin_client: AsyncClient):
    response = await authenticated_admin_client.get(
        "/candidates/create", follow_redirects=False
    )
    assert response.status_code == 200
    assert b"Add New Candidate" in response.content


@pytest.mark.asyncio
async def test_create_candidate_form_interviewer_redirected(
    authenticated_interviewer_client: AsyncClient,
):
    response = await authenticated_interviewer_client.get(
        "/candidates/create", follow_redirects=False
    )
    assert response.status_code == 302
    assert "/candidates/" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_create_candidate_success(authenticated_hr_client: AsyncClient):
    response = await authenticated_hr_client.post(
        "/candidates/create",
        data={
            "first_name": "John",
            "last_name": "Smith",
            "email": "john.smith@example.com",
            "phone": "+1555123456",
            "linkedin_url": "https://linkedin.com/in/johnsmith",
            "resume_text": "Experienced developer with 5 years of Python experience.",
            "skills": "Python, FastAPI, Docker",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert "/candidates/" in location


@pytest.mark.asyncio
async def test_create_candidate_with_skills(
    authenticated_hr_client: AsyncClient,
    db_session: AsyncSession,
):
    response = await authenticated_hr_client.post(
        "/candidates/create",
        data={
            "first_name": "Alice",
            "last_name": "Johnson",
            "email": "alice.johnson@example.com",
            "phone": "",
            "linkedin_url": "",
            "resume_text": "Full stack developer.",
            "skills": "JavaScript, React, Node.js",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    from sqlalchemy import select

    result = await db_session.execute(
        select(Candidate).where(Candidate.email == "alice.johnson@example.com")
    )
    candidate = result.scalars().first()
    assert candidate is not None
    assert candidate.name == "Alice Johnson"

    from sqlalchemy.orm import selectinload

    result = await db_session.execute(
        select(Candidate)
        .options(selectinload(Candidate.skills))
        .where(Candidate.id == candidate.id)
    )
    candidate = result.scalars().first()
    skill_names = {s.name for s in candidate.skills}
    assert "JavaScript" in skill_names
    assert "React" in skill_names
    assert "Node.js" in skill_names


@pytest.mark.asyncio
async def test_create_candidate_without_skills(authenticated_hr_client: AsyncClient):
    response = await authenticated_hr_client.post(
        "/candidates/create",
        data={
            "first_name": "Bob",
            "last_name": "Williams",
            "email": "bob.williams@example.com",
            "phone": "",
            "linkedin_url": "",
            "resume_text": "Junior developer looking for opportunities.",
            "skills": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert "/candidates/" in location


@pytest.mark.asyncio
async def test_create_candidate_duplicate_email(
    authenticated_hr_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_hr_client.post(
        "/candidates/create",
        data={
            "first_name": "Another",
            "last_name": "Person",
            "email": sample_candidate.email,
            "phone": "",
            "linkedin_url": "",
            "resume_text": "Some resume text here.",
            "skills": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert b"already exists" in response.content


@pytest.mark.asyncio
async def test_create_candidate_interviewer_cannot_create(
    authenticated_interviewer_client: AsyncClient,
):
    response = await authenticated_interviewer_client.post(
        "/candidates/create",
        data={
            "first_name": "Test",
            "last_name": "User",
            "email": "test.user.interviewer@example.com",
            "phone": "",
            "linkedin_url": "",
            "resume_text": "Some resume.",
            "skills": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/candidates/" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_candidate_detail_page(
    authenticated_hr_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_hr_client.get(
        f"/candidates/{sample_candidate.id}", follow_redirects=False
    )
    assert response.status_code == 200
    assert sample_candidate.name.encode() in response.content
    assert sample_candidate.email.encode() in response.content


@pytest.mark.asyncio
async def test_candidate_detail_not_found(authenticated_hr_client: AsyncClient):
    response = await authenticated_hr_client.get(
        "/candidates/99999", follow_redirects=False
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_candidate_detail_shows_skills(
    authenticated_hr_client: AsyncClient,
    db_session: AsyncSession,
    sample_candidate: Candidate,
):
    skill = Skill(name="FastAPI")
    db_session.add(skill)
    await db_session.flush()
    await db_session.refresh(skill)

    sample_candidate.skills.append(skill)
    await db_session.flush()

    response = await authenticated_hr_client.get(
        f"/candidates/{sample_candidate.id}", follow_redirects=False
    )
    assert response.status_code == 200
    assert b"FastAPI" in response.content


@pytest.mark.asyncio
async def test_candidate_detail_shows_applications(
    authenticated_hr_client: AsyncClient,
    sample_candidate: Candidate,
    sample_application: Application,
):
    response = await authenticated_hr_client.get(
        f"/candidates/{sample_candidate.id}", follow_redirects=False
    )
    assert response.status_code == 200
    assert b"Applications" in response.content


@pytest.mark.asyncio
async def test_candidate_detail_shows_resume(
    authenticated_hr_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_hr_client.get(
        f"/candidates/{sample_candidate.id}", follow_redirects=False
    )
    assert response.status_code == 200
    assert sample_candidate.resume_text.encode() in response.content


@pytest.mark.asyncio
async def test_edit_candidate_form_requires_login(
    client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await client.get(
        f"/candidates/{sample_candidate.id}/edit", follow_redirects=False
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_edit_candidate_form_hr_access(
    authenticated_hr_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_hr_client.get(
        f"/candidates/{sample_candidate.id}/edit", follow_redirects=False
    )
    assert response.status_code == 200
    assert b"Edit Candidate" in response.content


@pytest.mark.asyncio
async def test_edit_candidate_form_interviewer_redirected(
    authenticated_interviewer_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_interviewer_client.get(
        f"/candidates/{sample_candidate.id}/edit", follow_redirects=False
    )
    assert response.status_code == 302
    assert f"/candidates/{sample_candidate.id}" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_update_candidate_success(
    authenticated_hr_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_hr_client.post(
        f"/candidates/{sample_candidate.id}/edit",
        data={
            "first_name": "Jane",
            "last_name": "Updated",
            "email": "jane.updated@example.com",
            "phone": "+9876543210",
            "linkedin_url": "https://linkedin.com/in/janeupdated",
            "resume_text": "Updated resume text with more experience.",
            "skills": "Python, Go",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert f"/candidates/{sample_candidate.id}" in location


@pytest.mark.asyncio
async def test_update_candidate_changes_name(
    authenticated_hr_client: AsyncClient,
    sample_candidate: Candidate,
    db_session: AsyncSession,
):
    await authenticated_hr_client.post(
        f"/candidates/{sample_candidate.id}/edit",
        data={
            "first_name": "Updated",
            "last_name": "Name",
            "email": sample_candidate.email,
            "phone": "",
            "linkedin_url": "",
            "resume_text": sample_candidate.resume_text,
            "skills": "",
        },
        follow_redirects=False,
    )

    from sqlalchemy import select

    result = await db_session.execute(
        select(Candidate).where(Candidate.id == sample_candidate.id)
    )
    updated = result.scalars().first()
    assert updated is not None
    assert updated.name == "Updated Name"


@pytest.mark.asyncio
async def test_update_candidate_changes_skills(
    authenticated_hr_client: AsyncClient,
    sample_candidate: Candidate,
    db_session: AsyncSession,
):
    await authenticated_hr_client.post(
        f"/candidates/{sample_candidate.id}/edit",
        data={
            "first_name": "Jane",
            "last_name": "Doe",
            "email": sample_candidate.email,
            "phone": "",
            "linkedin_url": "",
            "resume_text": sample_candidate.resume_text,
            "skills": "Rust, Kubernetes, Terraform",
        },
        follow_redirects=False,
    )

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    result = await db_session.execute(
        select(Candidate)
        .options(selectinload(Candidate.skills))
        .where(Candidate.id == sample_candidate.id)
    )
    updated = result.scalars().first()
    assert updated is not None
    skill_names = {s.name for s in updated.skills}
    assert "Rust" in skill_names
    assert "Kubernetes" in skill_names
    assert "Terraform" in skill_names


@pytest.mark.asyncio
async def test_update_candidate_clear_skills(
    authenticated_hr_client: AsyncClient,
    db_session: AsyncSession,
    sample_candidate: Candidate,
):
    skill = Skill(name="OldSkill")
    db_session.add(skill)
    await db_session.flush()
    await db_session.refresh(skill)
    sample_candidate.skills.append(skill)
    await db_session.flush()

    await authenticated_hr_client.post(
        f"/candidates/{sample_candidate.id}/edit",
        data={
            "first_name": "Jane",
            "last_name": "Doe",
            "email": sample_candidate.email,
            "phone": "",
            "linkedin_url": "",
            "resume_text": sample_candidate.resume_text,
            "skills": "",
        },
        follow_redirects=False,
    )

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    result = await db_session.execute(
        select(Candidate)
        .options(selectinload(Candidate.skills))
        .where(Candidate.id == sample_candidate.id)
    )
    updated = result.scalars().first()
    assert updated is not None
    assert len(updated.skills) == 0


@pytest.mark.asyncio
async def test_update_candidate_duplicate_email(
    authenticated_hr_client: AsyncClient,
    db_session: AsyncSession,
    sample_candidate: Candidate,
):
    other_candidate = Candidate(
        name="Other Person",
        email="other.person@example.com",
        resume_text="Other resume.",
    )
    db_session.add(other_candidate)
    await db_session.flush()

    response = await authenticated_hr_client.post(
        f"/candidates/{sample_candidate.id}/edit",
        data={
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "other.person@example.com",
            "phone": "",
            "linkedin_url": "",
            "resume_text": sample_candidate.resume_text,
            "skills": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert b"already exists" in response.content


@pytest.mark.asyncio
async def test_update_candidate_interviewer_cannot_edit(
    authenticated_interviewer_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_interviewer_client.post(
        f"/candidates/{sample_candidate.id}/edit",
        data={
            "first_name": "Hacked",
            "last_name": "Name",
            "email": sample_candidate.email,
            "phone": "",
            "linkedin_url": "",
            "resume_text": "Hacked resume.",
            "skills": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert f"/candidates/{sample_candidate.id}" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_edit_candidate_not_found(authenticated_hr_client: AsyncClient):
    response = await authenticated_hr_client.get(
        "/candidates/99999/edit", follow_redirects=False
    )
    assert response.status_code == 302
    assert "/candidates/" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_candidate_service_create_candidate(
    db_session: AsyncSession,
    hr_user: User,
):
    from app.services.candidate_service import CandidateService

    service = CandidateService(db_session)
    candidate = await service.create_candidate(
        name="Service Test",
        email="service.test@example.com",
        resume_text="Created via service layer.",
        user=hr_user,
        phone="+1111111111",
        linkedin_url="https://linkedin.com/in/servicetest",
        skill_names=["Python", "SQL"],
    )

    assert candidate.id is not None
    assert candidate.name == "Service Test"
    assert candidate.email == "service.test@example.com"
    assert candidate.phone == "+1111111111"


@pytest.mark.asyncio
async def test_candidate_service_create_duplicate_email(
    db_session: AsyncSession,
    hr_user: User,
    sample_candidate: Candidate,
):
    from app.services.candidate_service import CandidateService

    service = CandidateService(db_session)
    with pytest.raises(ValueError, match="already exists"):
        await service.create_candidate(
            name="Duplicate",
            email=sample_candidate.email,
            resume_text="Duplicate email test.",
            user=hr_user,
        )


@pytest.mark.asyncio
async def test_candidate_service_update_candidate(
    db_session: AsyncSession,
    hr_user: User,
    sample_candidate: Candidate,
):
    from app.services.candidate_service import CandidateService

    service = CandidateService(db_session)
    updated = await service.update_candidate(
        candidate_id=sample_candidate.id,
        user=hr_user,
        name="Updated Via Service",
        email="updated.service@example.com",
    )

    assert updated.name == "Updated Via Service"
    assert updated.email == "updated.service@example.com"


@pytest.mark.asyncio
async def test_candidate_service_update_not_found(
    db_session: AsyncSession,
    hr_user: User,
):
    from app.services.candidate_service import CandidateService

    service = CandidateService(db_session)
    with pytest.raises(ValueError, match="not found"):
        await service.update_candidate(
            candidate_id=99999,
            user=hr_user,
            name="Ghost",
        )


@pytest.mark.asyncio
async def test_candidate_service_get_by_id(
    db_session: AsyncSession,
    sample_candidate: Candidate,
):
    from app.services.candidate_service import CandidateService

    service = CandidateService(db_session)
    result = await service.get_candidate_by_id(sample_candidate.id)
    assert result is not None
    assert result.id == sample_candidate.id
    assert result.name == sample_candidate.name


@pytest.mark.asyncio
async def test_candidate_service_get_by_id_not_found(db_session: AsyncSession):
    from app.services.candidate_service import CandidateService

    service = CandidateService(db_session)
    result = await service.get_candidate_by_id(99999)
    assert result is None


@pytest.mark.asyncio
async def test_candidate_service_list_candidates_pagination(
    db_session: AsyncSession,
    hr_user: User,
):
    from app.services.candidate_service import CandidateService

    service = CandidateService(db_session)

    for i in range(5):
        await service.create_candidate(
            name=f"Candidate {i}",
            email=f"candidate{i}@pagination.com",
            resume_text=f"Resume for candidate {i}.",
            user=hr_user,
        )

    result = await service.list_candidates(page=1, page_size=3)
    assert result["total"] >= 5
    assert len(result["items"]) == 3
    assert result["page"] == 1

    result2 = await service.list_candidates(page=2, page_size=3)
    assert len(result2["items"]) >= 2
    assert result2["page"] == 2


@pytest.mark.asyncio
async def test_candidate_service_add_skill(
    db_session: AsyncSession,
    hr_user: User,
    sample_candidate: Candidate,
):
    from app.services.candidate_service import CandidateService

    service = CandidateService(db_session)
    updated = await service.add_skill_to_candidate(
        candidate_id=sample_candidate.id,
        skill_name="NewSkill",
        user=hr_user,
    )

    skill_names = {s.name for s in updated.skills}
    assert "NewSkill" in skill_names


@pytest.mark.asyncio
async def test_candidate_service_add_duplicate_skill(
    db_session: AsyncSession,
    hr_user: User,
    sample_candidate: Candidate,
):
    from app.services.candidate_service import CandidateService

    service = CandidateService(db_session)
    await service.add_skill_to_candidate(
        candidate_id=sample_candidate.id,
        skill_name="DuplicateSkill",
        user=hr_user,
    )
    updated = await service.add_skill_to_candidate(
        candidate_id=sample_candidate.id,
        skill_name="DuplicateSkill",
        user=hr_user,
    )

    duplicate_count = sum(1 for s in updated.skills if s.name == "DuplicateSkill")
    assert duplicate_count == 1


@pytest.mark.asyncio
async def test_candidate_service_remove_skill(
    db_session: AsyncSession,
    hr_user: User,
    sample_candidate: Candidate,
):
    from app.services.candidate_service import CandidateService

    service = CandidateService(db_session)

    updated = await service.add_skill_to_candidate(
        candidate_id=sample_candidate.id,
        skill_name="RemovableSkill",
        user=hr_user,
    )

    skill_to_remove = None
    for s in updated.skills:
        if s.name == "RemovableSkill":
            skill_to_remove = s
            break
    assert skill_to_remove is not None

    updated = await service.remove_skill_from_candidate(
        candidate_id=sample_candidate.id,
        skill_id=skill_to_remove.id,
        user=hr_user,
    )

    skill_names = {s.name for s in updated.skills}
    assert "RemovableSkill" not in skill_names


@pytest.mark.asyncio
async def test_candidate_service_get_or_create_skill(
    db_session: AsyncSession,
):
    from app.services.candidate_service import CandidateService

    service = CandidateService(db_session)

    skill1 = await service.get_or_create_skill("UniqueSkill")
    assert skill1.id is not None
    assert skill1.name == "UniqueSkill"

    skill2 = await service.get_or_create_skill("uniqueskill")
    assert skill2.id == skill1.id


@pytest.mark.asyncio
async def test_candidate_service_get_all_skills(
    db_session: AsyncSession,
):
    from app.services.candidate_service import CandidateService

    service = CandidateService(db_session)

    await service.get_or_create_skill("SkillA")
    await service.get_or_create_skill("SkillB")
    await service.get_or_create_skill("SkillC")

    all_skills = await service.get_all_skills()
    skill_names = {s.name for s in all_skills}
    assert "SkillA" in skill_names
    assert "SkillB" in skill_names
    assert "SkillC" in skill_names


@pytest.mark.asyncio
async def test_candidate_detail_shows_linkedin(
    authenticated_hr_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_hr_client.get(
        f"/candidates/{sample_candidate.id}", follow_redirects=False
    )
    assert response.status_code == 200
    assert b"linkedin.com" in response.content


@pytest.mark.asyncio
async def test_candidates_list_interviewer_can_view(
    authenticated_interviewer_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_interviewer_client.get(
        "/candidates/", follow_redirects=False
    )
    assert response.status_code == 200
    assert sample_candidate.name.encode() in response.content


@pytest.mark.asyncio
async def test_candidate_detail_interviewer_can_view(
    authenticated_interviewer_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_interviewer_client.get(
        f"/candidates/{sample_candidate.id}", follow_redirects=False
    )
    assert response.status_code == 200
    assert sample_candidate.name.encode() in response.content


@pytest.mark.asyncio
async def test_candidate_detail_shows_application_with_job(
    authenticated_hr_client: AsyncClient,
    sample_candidate: Candidate,
    sample_application: Application,
    sample_job: Job,
):
    response = await authenticated_hr_client.get(
        f"/candidates/{sample_candidate.id}", follow_redirects=False
    )
    assert response.status_code == 200
    assert sample_job.title.encode() in response.content


@pytest.mark.asyncio
async def test_hiring_manager_can_view_candidates(
    authenticated_manager_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_manager_client.get(
        "/candidates/", follow_redirects=False
    )
    assert response.status_code == 200
    assert sample_candidate.name.encode() in response.content


@pytest.mark.asyncio
async def test_hiring_manager_cannot_create_candidate(
    authenticated_manager_client: AsyncClient,
):
    response = await authenticated_manager_client.get(
        "/candidates/create", follow_redirects=False
    )
    assert response.status_code == 302
    assert "/candidates/" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_hiring_manager_cannot_edit_candidate(
    authenticated_manager_client: AsyncClient,
    sample_candidate: Candidate,
):
    response = await authenticated_manager_client.get(
        f"/candidates/{sample_candidate.id}/edit", follow_redirects=False
    )
    assert response.status_code == 302
    assert f"/candidates/{sample_candidate.id}" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_create_candidate_minimal_fields(authenticated_hr_client: AsyncClient):
    response = await authenticated_hr_client.post(
        "/candidates/create",
        data={
            "first_name": "Minimal",
            "last_name": "Candidate",
            "email": "minimal.candidate@example.com",
            "phone": "",
            "linkedin_url": "",
            "resume_text": "Minimal resume.",
            "skills": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert "/candidates/" in location


@pytest.mark.asyncio
async def test_candidate_service_search_by_name(
    db_session: AsyncSession,
    hr_user: User,
    sample_candidate: Candidate,
):
    from app.services.candidate_service import CandidateService

    service = CandidateService(db_session)
    result = await service.list_candidates(search="Jane")
    assert result["total"] >= 1
    found_names = [c.name for c in result["items"]]
    assert sample_candidate.name in found_names


@pytest.mark.asyncio
async def test_candidate_service_search_by_email(
    db_session: AsyncSession,
    hr_user: User,
    sample_candidate: Candidate,
):
    from app.services.candidate_service import CandidateService

    service = CandidateService(db_session)
    result = await service.list_candidates(search="jane.doe@example")
    assert result["total"] >= 1
    found_emails = [c.email for c in result["items"]]
    assert sample_candidate.email in found_emails