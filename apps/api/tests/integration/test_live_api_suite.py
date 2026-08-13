"""
Comprehensive Live API Testing & Edge Case Verification Suite
Tests all 10 authentication and user management API endpoints via live HTTP requests.
"""

from unittest.mock import patch
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import Base, get_db
from app.main import app


@pytest.mark.asyncio
async def test_complete_auth_api_lifecycle_and_edge_cases():
    """
    Executes terminal HTTP requests against all authentication & user management APIs:
    1. POST /api/v1/auth/register (Success)
    2. POST /api/v1/auth/register (Duplicate Email -> 409)
    3. POST /api/v1/auth/login (Success with cookies)
    4. POST /api/v1/auth/login (Invalid Password -> 401)
    5. GET  /api/v1/users/me (Authenticated with cookie -> 200)
    6. GET  /api/v1/users/me (Unauthenticated -> 401)
    7. PUT  /api/v1/users/me (Update Profile -> 200)
    8. POST /api/v1/auth/refresh (Token Rotation -> 200)
    9. GET  /api/v1/auth/google/login (Generate OAuth URL & State Cookie -> 200)
    10. POST /api/v1/auth/google (Authenticate Google ID token -> 200)
    11. POST /api/v1/auth/register (Google Email Conflict -> 409)
    12. POST /api/v1/auth/login (Google Email Password Login Attempt -> 400)
    13. POST /api/v1/auth/google (Password Email Google Login Attempt -> 409)
    14. POST /api/v1/auth/logout (Clear cookies -> 200)
    15. GET  /api/v1/users/me (After Logout -> 401)
    """
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        print("\n--- Starting Live API Call Testing Suite ---")

        # 1. POST /auth/register (Success)
        reg_payload = {
            "email": "dev.test@example.com",
            "password": "Password123!",
            "name": "Dev Tester",
        }
        res_reg = await client.post("/api/v1/auth/register", json=reg_payload)
        assert res_reg.status_code == 201, f"Register failed: {res_reg.text}"
        assert "access_token" in res_reg.cookies
        assert "refresh_token" in res_reg.cookies
        print("[OK] POST /api/v1/auth/register -> 201 Created (Cookies attached)")

        # 2. POST /auth/register (Duplicate -> 409)
        res_dup_reg = await client.post("/api/v1/auth/register", json=reg_payload)
        assert res_dup_reg.status_code == 409
        print("[OK] POST /api/v1/auth/register (Duplicate) -> 409 Conflict")

        # 3. POST /auth/login (Success)
        login_payload = {
            "email": "dev.test@example.com",
            "password": "Password123!",
        }
        res_login = await client.post("/api/v1/auth/login", json=login_payload)
        assert res_login.status_code == 200
        assert "access_token" in res_login.cookies
        print("[OK] POST /api/v1/auth/login -> 200 OK")

        # 4. POST /auth/login (Bad Password -> 401)
        bad_login_payload = {
            "email": "dev.test@example.com",
            "password": "WrongPassword999!",
        }
        res_bad_login = await client.post("/api/v1/auth/login", json=bad_login_payload)
        assert res_bad_login.status_code == 401
        print("[OK] POST /api/v1/auth/login (Wrong Password) -> 401 Unauthorized")

        # 5. GET /users/me (Authenticated via Cookie)
        res_me = await client.get("/api/v1/users/me")
        assert res_me.status_code == 200
        assert res_me.json()["email"] == "dev.test@example.com"
        print("[OK] GET /api/v1/users/me -> 200 OK (User authenticated)")

        # 6. PUT /users/me (Update Name)
        res_update = await client.put("/api/v1/users/me", json={"name": "Dev Lead Tester"})
        assert res_update.status_code == 200
        assert res_update.json()["name"] == "Dev Lead Tester"
        print("[OK] PUT /api/v1/users/me -> 200 OK (Profile updated)")

        # 7. POST /auth/refresh (Token Rotation)
        res_refresh = await client.post("/api/v1/auth/refresh")
        assert res_refresh.status_code == 200
        assert "access_token" in res_refresh.cookies
        print("[OK] POST /api/v1/auth/refresh -> 200 OK (Tokens rotated)")

        # 8. GET /auth/google/login
        with patch("app.core.config.settings.GOOGLE_CLIENT_ID", "test_client_123"):
            res_glogin = await client.get("/api/v1/auth/google/login")
            assert res_glogin.status_code == 200
            assert "accounts.google.com" in res_glogin.json()["url"]
            assert "oauth_state" in res_glogin.cookies
            print("[OK] GET /api/v1/auth/google/login -> 200 OK (Redirect URL & State Cookie set)")

        # 9. POST /auth/google (Authenticate Google ID Token)
        mock_google_id = {
            "sub": "google_sub_777777",
            "email": "google.dev@example.com",
            "name": "Google Dev User",
            "email_verified": True,
        }
        with patch("app.modules.users.users_routes.id_token.verify_oauth2_token", return_value=mock_google_id), \
             patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_google_id):
            res_gauth = await client.post("/api/v1/auth/google", json={"id_token": "valid_token_mock"})
            assert res_gauth.status_code == 200
            assert res_gauth.json()["user"]["email"] == "google.dev@example.com"
            print("[OK] POST /api/v1/auth/google -> 200 OK (Google user created & logged in)")

        # 10. POST /auth/register with Google email -> 409 Conflict
        res_g_reg = await client.post(
            "/api/v1/auth/register",
            json={"email": "google.dev@example.com", "password": "Password123!", "name": "Fake User"},
        )
        assert res_g_reg.status_code == 409
        print("[OK] Edge Case: Register with Google email -> 409 Conflict")

        # 11. POST /auth/login with Google email -> 400 Bad Request
        res_g_pwd = await client.post(
            "/api/v1/auth/login",
            json={"email": "google.dev@example.com", "password": "Password123!"},
        )
        assert res_g_pwd.status_code == 400
        print("[OK] Edge Case: Password login on Google account -> 400 Bad Request")

        # 12. POST /auth/google with Password email -> 409 Conflict
        mock_pwd_user_g = {
            "sub": "google_sub_666666",
            "email": "dev.test@example.com",
            "name": "Dev Tester",
            "email_verified": True,
        }
        with patch("app.modules.users.users_routes.id_token.verify_oauth2_token", return_value=mock_pwd_user_g), \
             patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_pwd_user_g):
            res_pwd_g = await client.post("/api/v1/auth/google", json={"id_token": "valid_token_mock"})
            assert res_pwd_g.status_code == 409
            print("[OK] Edge Case: Google login on Password account -> 409 Conflict")

        # 13. POST /auth/logout
        res_logout = await client.post("/api/v1/auth/logout")
        assert res_logout.status_code == 200
        print("[OK] POST /api/v1/auth/logout -> 200 OK (Cookies cleared)")

        # 14. GET /users/me (After Logout -> 401)
        res_unauth = await client.get("/api/v1/users/me")
        assert res_unauth.status_code == 401
        print("[OK] GET /api/v1/users/me (After Logout) -> 401 Unauthorized")

        print("--- All Live API Call Tests Successfully Passed ---")

    app.dependency_overrides.clear()
    await test_engine.dispose()
