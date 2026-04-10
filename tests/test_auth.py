import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash, verify_password, create_session_cookie, decode_session_cookie
from app.models.user import User
from app.services.auth_service import AuthService
from tests.conftest import create_test_user, login_user


class TestPasswordHashing:
    """Tests for password hashing and verification utilities."""

    def test_get_password_hash_returns_hashed_string(self):
        plain = "SecurePass123"
        hashed = get_password_hash(plain)
        assert hashed is not None
        assert isinstance(hashed, str)
        assert hashed != plain

    def test_verify_password_correct(self):
        plain = "SecurePass123"
        hashed = get_password_hash(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_password_incorrect(self):
        plain = "SecurePass123"
        hashed = get_password_hash(plain)
        assert verify_password("WrongPassword1", hashed) is False

    def test_different_hashes_for_same_password(self):
        plain = "SecurePass123"
        hash1 = get_password_hash(plain)
        hash2 = get_password_hash(plain)
        assert hash1 != hash2
        assert verify_password(plain, hash1) is True
        assert verify_password(plain, hash2) is True


class TestSessionCookie:
    """Tests for session cookie creation and decoding."""

    def test_create_session_cookie_returns_string(self):
        cookie = create_session_cookie(user_id=1, username="testuser", role="Interviewer")
        assert cookie is not None
        assert isinstance(cookie, str)
        assert len(cookie) > 0

    def test_decode_session_cookie_valid(self):
        cookie = create_session_cookie(user_id=42, username="alice", role="HR Recruiter")
        data = decode_session_cookie(cookie)
        assert data is not None
        assert data["user_id"] == 42
        assert data["username"] == "alice"
        assert data["role"] == "HR Recruiter"

    def test_decode_session_cookie_invalid(self):
        data = decode_session_cookie("invalid-cookie-value")
        assert data is None

    def test_decode_session_cookie_tampered(self):
        cookie = create_session_cookie(user_id=1, username="testuser", role="Interviewer")
        tampered = cookie + "tampered"
        data = decode_session_cookie(tampered)
        assert data is None

    def test_decode_session_cookie_empty_string(self):
        data = decode_session_cookie("")
        assert data is None

    def test_decode_session_cookie_expired(self):
        cookie = create_session_cookie(user_id=1, username="testuser", role="Interviewer")
        data = decode_session_cookie(cookie, max_age=0)
        assert data is None


class TestAuthService:
    """Tests for AuthService login and register methods."""

    @pytest.mark.asyncio
    async def test_login_valid_credentials(self, db_session: AsyncSession):
        user = await create_test_user(
            db_session,
            username="login_valid",
            password="TestPass123",
            role="Interviewer",
        )
        auth_service = AuthService(db_session)
        result = await auth_service.login("login_valid", "TestPass123")
        assert result is not None
        assert result.id == user.id
        assert result.username == "login_valid"

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, db_session: AsyncSession):
        await create_test_user(
            db_session,
            username="login_badpw",
            password="TestPass123",
            role="Interviewer",
        )
        auth_service = AuthService(db_session)
        result = await auth_service.login("login_badpw", "WrongPassword1")
        assert result is None

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, db_session: AsyncSession):
        auth_service = AuthService(db_session)
        result = await auth_service.login("nonexistent_user", "TestPass123")
        assert result is None

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, db_session: AsyncSession):
        await create_test_user(
            db_session,
            username="login_inactive",
            password="TestPass123",
            role="Interviewer",
            is_active=False,
        )
        auth_service = AuthService(db_session)
        result = await auth_service.login("login_inactive", "TestPass123")
        assert result is None

    @pytest.mark.asyncio
    async def test_register_new_user(self, db_session: AsyncSession):
        auth_service = AuthService(db_session)
        user = await auth_service.register(
            username="new_user",
            password="NewPass123",
            email="new_user@test.com",
            full_name="New User",
            role="Interviewer",
        )
        assert user is not None
        assert user.username == "new_user"
        assert user.role == "Interviewer"
        assert user.email == "new_user@test.com"
        assert user.full_name == "New User"
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_register_default_role_is_interviewer(self, db_session: AsyncSession):
        auth_service = AuthService(db_session)
        user = await auth_service.register(
            username="default_role_user",
            password="NewPass123",
        )
        assert user.role == "Interviewer"

    @pytest.mark.asyncio
    async def test_register_duplicate_username_raises(self, db_session: AsyncSession):
        await create_test_user(
            db_session,
            username="dup_user",
            password="TestPass123",
        )
        auth_service = AuthService(db_session)
        with pytest.raises(ValueError, match="Username already exists"):
            await auth_service.register(
                username="dup_user",
                password="AnotherPass1",
            )

    @pytest.mark.asyncio
    async def test_register_duplicate_email_raises(self, db_session: AsyncSession):
        await create_test_user(
            db_session,
            username="email_user1",
            password="TestPass123",
            email="duplicate@test.com",
        )
        auth_service = AuthService(db_session)
        with pytest.raises(ValueError, match="Email already exists"):
            await auth_service.register(
                username="email_user2",
                password="AnotherPass1",
                email="duplicate@test.com",
            )

    @pytest.mark.asyncio
    async def test_register_password_is_hashed(self, db_session: AsyncSession):
        auth_service = AuthService(db_session)
        user = await auth_service.register(
            username="hashed_pw_user",
            password="PlainText123",
        )
        assert user.hashed_password != "PlainText123"
        assert verify_password("PlainText123", user.hashed_password) is True

    @pytest.mark.asyncio
    async def test_create_session_returns_valid_cookie(self, db_session: AsyncSession):
        user = await create_test_user(
            db_session,
            username="session_user",
            role="HR Recruiter",
        )
        auth_service = AuthService(db_session)
        cookie = auth_service.create_session(user)
        assert cookie is not None
        data = decode_session_cookie(cookie)
        assert data is not None
        assert data["user_id"] == user.id
        assert data["username"] == "session_user"
        assert data["role"] == "HR Recruiter"


class TestLoginEndpoint:
    """Tests for the POST /login endpoint."""

    @pytest.mark.asyncio
    async def test_login_page_renders(self, client: AsyncClient):
        response = await client.get("/login")
        assert response.status_code == 200
        assert "Sign In" in response.text

    @pytest.mark.asyncio
    async def test_login_success_sets_cookie_and_redirects(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await create_test_user(
            db_session,
            username="login_endpoint_user",
            password="TestPass123",
            role="System Admin",
        )
        response = await client.post(
            "/login",
            data={"username": "login_endpoint_user", "password": "TestPass123"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert settings.SESSION_COOKIE_NAME in response.cookies
        assert "/dashboard" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_login_invalid_credentials_returns_401(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await create_test_user(
            db_session,
            username="login_fail_user",
            password="TestPass123",
        )
        response = await client.post(
            "/login",
            data={"username": "login_fail_user", "password": "WrongPassword1"},
            follow_redirects=False,
        )
        assert response.status_code == 401
        assert "Invalid username or password" in response.text

    @pytest.mark.asyncio
    async def test_login_nonexistent_user_returns_401(self, client: AsyncClient):
        response = await client.post(
            "/login",
            data={"username": "ghost_user", "password": "TestPass123"},
            follow_redirects=False,
        )
        assert response.status_code == 401
        assert "Invalid username or password" in response.text

    @pytest.mark.asyncio
    async def test_login_redirects_admin_to_dashboard(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await create_test_user(
            db_session,
            username="admin_redirect",
            password="TestPass123",
            role="System Admin",
        )
        response = await client.post(
            "/login",
            data={"username": "admin_redirect", "password": "TestPass123"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        location = response.headers.get("location", "")
        assert "/dashboard" in location

    @pytest.mark.asyncio
    async def test_login_redirects_hr_to_dashboard(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await create_test_user(
            db_session,
            username="hr_redirect",
            password="TestPass123",
            role="HR Recruiter",
        )
        response = await client.post(
            "/login",
            data={"username": "hr_redirect", "password": "TestPass123"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        location = response.headers.get("location", "")
        assert "/dashboard" in location

    @pytest.mark.asyncio
    async def test_login_redirects_interviewer_to_my_interviews(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await create_test_user(
            db_session,
            username="interviewer_redirect",
            password="TestPass123",
            role="Interviewer",
        )
        response = await client.post(
            "/login",
            data={"username": "interviewer_redirect", "password": "TestPass123"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        location = response.headers.get("location", "")
        assert "/interviews/my" in location

    @pytest.mark.asyncio
    async def test_login_redirects_hiring_manager_to_dashboard(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await create_test_user(
            db_session,
            username="manager_redirect",
            password="TestPass123",
            role="Hiring Manager",
        )
        response = await client.post(
            "/login",
            data={"username": "manager_redirect", "password": "TestPass123"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        location = response.headers.get("location", "")
        assert "/dashboard" in location

    @pytest.mark.asyncio
    async def test_login_page_redirects_if_already_logged_in(
        self, authenticated_admin_client: AsyncClient
    ):
        response = await authenticated_admin_client.get(
            "/login",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/dashboard" in response.headers.get("location", "")


class TestRegisterEndpoint:
    """Tests for the POST /register endpoint."""

    @pytest.mark.asyncio
    async def test_register_page_renders(self, client: AsyncClient):
        response = await client.get("/register")
        assert response.status_code == 200
        assert "Create your account" in response.text

    @pytest.mark.asyncio
    async def test_register_success_creates_user_and_redirects(
        self, client: AsyncClient
    ):
        response = await client.post(
            "/register",
            data={
                "username": "newreg_user",
                "password": "SecurePass1",
                "confirm_password": "SecurePass1",
                "email": "newreg@test.com",
                "full_name": "New Reg User",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert settings.SESSION_COOKIE_NAME in response.cookies

    @pytest.mark.asyncio
    async def test_register_assigns_interviewer_role(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        response = await client.post(
            "/register",
            data={
                "username": "role_check_user",
                "password": "SecurePass1",
                "confirm_password": "SecurePass1",
                "email": "rolecheck@test.com",
                "full_name": "Role Check",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        location = response.headers.get("location", "")
        assert "/interviews/my" in location

    @pytest.mark.asyncio
    async def test_register_duplicate_username_returns_400(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await create_test_user(
            db_session,
            username="existing_user",
            password="TestPass123",
        )
        response = await client.post(
            "/register",
            data={
                "username": "existing_user",
                "password": "SecurePass1",
                "confirm_password": "SecurePass1",
                "email": "another@test.com",
                "full_name": "Another User",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "Username already exists" in response.text

    @pytest.mark.asyncio
    async def test_register_password_mismatch_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/register",
            data={
                "username": "mismatch_user",
                "password": "SecurePass1",
                "confirm_password": "DifferentPass1",
                "email": "mismatch@test.com",
                "full_name": "Mismatch User",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "Passwords do not match" in response.text

    @pytest.mark.asyncio
    async def test_register_short_password_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/register",
            data={
                "username": "shortpw_user",
                "password": "Ab1",
                "confirm_password": "Ab1",
                "email": "shortpw@test.com",
                "full_name": "Short PW",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "at least 8 characters" in response.text

    @pytest.mark.asyncio
    async def test_register_password_no_number_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/register",
            data={
                "username": "nonum_user",
                "password": "NoNumberHere",
                "confirm_password": "NoNumberHere",
                "email": "nonum@test.com",
                "full_name": "No Num",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "at least one number" in response.text

    @pytest.mark.asyncio
    async def test_register_password_no_letter_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/register",
            data={
                "username": "nolet_user",
                "password": "12345678",
                "confirm_password": "12345678",
                "email": "nolet@test.com",
                "full_name": "No Letter",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "at least one letter" in response.text

    @pytest.mark.asyncio
    async def test_register_short_username_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/register",
            data={
                "username": "ab",
                "password": "SecurePass1",
                "confirm_password": "SecurePass1",
                "email": "short@test.com",
                "full_name": "Short Name",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "between 3 and 32 characters" in response.text

    @pytest.mark.asyncio
    async def test_register_invalid_username_chars_returns_400(
        self, client: AsyncClient
    ):
        response = await client.post(
            "/register",
            data={
                "username": "bad user!",
                "password": "SecurePass1",
                "confirm_password": "SecurePass1",
                "email": "badchar@test.com",
                "full_name": "Bad Chars",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "alphanumeric" in response.text

    @pytest.mark.asyncio
    async def test_register_page_redirects_if_already_logged_in(
        self, authenticated_admin_client: AsyncClient
    ):
        response = await authenticated_admin_client.get(
            "/register",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/dashboard" in response.headers.get("location", "")


class TestLogoutEndpoint:
    """Tests for the POST /auth/logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_clears_session_cookie(
        self, authenticated_admin_client: AsyncClient
    ):
        response = await authenticated_admin_client.post(
            "/auth/logout",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/" == response.headers.get("location", "")

        cookie_header = response.headers.get("set-cookie", "")
        assert settings.SESSION_COOKIE_NAME in cookie_header

    @pytest.mark.asyncio
    async def test_logout_redirects_to_landing(
        self, authenticated_admin_client: AsyncClient
    ):
        response = await authenticated_admin_client.post(
            "/auth/logout",
            follow_redirects=False,
        )
        assert response.status_code == 302
        location = response.headers.get("location", "")
        assert location == "/"

    @pytest.mark.asyncio
    async def test_logout_without_session_still_redirects(self, client: AsyncClient):
        response = await client.post(
            "/auth/logout",
            follow_redirects=False,
        )
        assert response.status_code == 302
        location = response.headers.get("location", "")
        assert location == "/"


class TestProtectedRoutes:
    """Tests that protected routes require authentication."""

    @pytest.mark.asyncio
    async def test_dashboard_requires_login(self, client: AsyncClient):
        response = await client.get("/dashboard", follow_redirects=False)
        assert response.status_code in (401, 403, 302)

    @pytest.mark.asyncio
    async def test_dashboard_accessible_when_authenticated(
        self, authenticated_admin_client: AsyncClient
    ):
        response = await authenticated_admin_client.get(
            "/dashboard",
            follow_redirects=False,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_jobs_requires_login(self, client: AsyncClient):
        response = await client.get("/jobs", follow_redirects=False)
        assert response.status_code in (401, 403, 302)

    @pytest.mark.asyncio
    async def test_candidates_requires_login(self, client: AsyncClient):
        response = await client.get("/candidates", follow_redirects=False)
        assert response.status_code in (401, 403, 302)

    @pytest.mark.asyncio
    async def test_applications_requires_login(self, client: AsyncClient):
        response = await client.get("/applications", follow_redirects=False)
        assert response.status_code in (401, 403, 302)

    @pytest.mark.asyncio
    async def test_interviews_requires_login(self, client: AsyncClient):
        response = await client.get("/interviews/", follow_redirects=False)
        assert response.status_code in (401, 403, 302)


class TestSessionPersistence:
    """Tests that session cookies persist across requests."""

    @pytest.mark.asyncio
    async def test_session_cookie_persists_across_requests(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await create_test_user(
            db_session,
            username="persist_user",
            password="TestPass123",
            role="System Admin",
        )

        login_response = await client.post(
            "/login",
            data={"username": "persist_user", "password": "TestPass123"},
            follow_redirects=False,
        )
        assert login_response.status_code == 302
        assert settings.SESSION_COOKIE_NAME in login_response.cookies

        for key, value in login_response.cookies.items():
            client.cookies.set(key, value)

        dashboard_response = await client.get("/dashboard", follow_redirects=False)
        assert dashboard_response.status_code == 200
        assert "persist_user" in dashboard_response.text

    @pytest.mark.asyncio
    async def test_invalid_session_cookie_denied(self, client: AsyncClient):
        client.cookies.set(settings.SESSION_COOKIE_NAME, "invalid-garbage-cookie")
        response = await client.get("/dashboard", follow_redirects=False)
        assert response.status_code in (401, 403, 302)