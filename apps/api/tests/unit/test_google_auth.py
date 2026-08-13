"""
Unit & Integration Tests for Google OAuth Endpoints & Auth Edge Cases
"""

from unittest.mock import patch
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import Base, get_db
from app.main import app


@pytest.mark.asyncio
async def test_google_login_endpoint():
    """Verify GET /api/v1/auth/google/login returns authorization URL."""
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
        with patch("app.core.config.settings.GOOGLE_CLIENT_ID", "test_google_client_id"):
            resp = await client.get("/api/v1/auth/google/login")
            assert resp.status_code == 200
            data = resp.json()
            assert "url" in data
            assert "accounts.google.com" in data["url"]
            assert "test_google_client_id" in data["url"]
            assert "oauth_state" in resp.cookies

    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_google_id_token_verification_and_auth_edge_cases():
    """
    Verify:
    1. Creating account via Google OAuth
    2. Attempting normal password registration with Google email -> Rejects with 409
    3. Attempting normal password login on Google account -> Rejects with 400
    4. Registering password account, then attempting Google login on unlinked account -> Rejects with 409
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

    mock_google_user = {
        "sub": "google_sub_999999",
        "email": "guser@example.com",
        "name": "Google User",
        "email_verified": True,
    }

    with patch("app.modules.users.users_routes.id_token.verify_oauth2_token", return_value=mock_google_user), \
         patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_google_user):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            # 1. Sign in via Google -> New Google user created
            resp = await client.post(
                "/api/v1/auth/google",
                json={"id_token": "mock_google_id_token"},
            )
            assert resp.status_code == 200
            assert resp.json()["user"]["email"] == "guser@example.com"

            # 2. Attempt normal password registration with Google email -> 409 Conflict
            reg_fail = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "guser@example.com",
                    "password": "Password123!",
                    "name": "Duplicate User",
                },
            )
            assert reg_fail.status_code == 409
            assert "Google Sign-In" in reg_fail.json()["detail"]

            # 3. Attempt normal password login on Google account -> 400 Bad Request
            login_fail = await client.post(
                "/api/v1/auth/login",
                json={"email": "guser@example.com", "password": "Password123!"},
            )
            assert login_fail.status_code == 400
            assert "Google Sign-In" in login_fail.json()["detail"]

            # 4. Register a normal password account
            pwd_reg = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "passworduser@example.com",
                    "password": "Password123!",
                    "name": "Password User",
                },
            )
            assert pwd_reg.status_code == 201

    # 5. Attempt Google Login with password user's email -> 409 Conflict
    mock_password_user_google = {
        "sub": "google_sub_888888",
        "email": "passworduser@example.com",
        "name": "Password User",
        "email_verified": True,
    }
    with patch("app.modules.users.users_routes.id_token.verify_oauth2_token", return_value=mock_password_user_google), \
         patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_password_user_google):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            pwd_google_fail = await client.post(
                "/api/v1/auth/google",
                json={"id_token": "mock_google_id_token"},
            )
            assert pwd_google_fail.status_code == 409
            assert "password authentication" in pwd_google_fail.json()["detail"]

    app.dependency_overrides.clear()
    await test_engine.dispose()
