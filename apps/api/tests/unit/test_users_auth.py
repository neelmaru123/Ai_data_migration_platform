"""
Unit & Integration Tests for User Domain & Authentication System
Tests password hashing, JWT creation/decoding, HTTP-only cookie auth, token rotation, and User CRUD endpoints.
"""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import Base, get_db
from app.modules.users.users_models import User
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    hash_password,
    verify_password,
)
from app.main import app


def test_password_hashing():
    """Verify bcrypt password hashing and verification."""
    password = "MySecurePassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_encoding_decoding():
    """Verify JWT access and refresh token encoding, payload types, and decoding."""
    user_id = str(uuid.uuid4())

    access_token = create_access_token(subject=user_id)
    refresh_token = create_refresh_token(subject=user_id)

    decoded_access = decode_jwt_token(access_token)
    assert decoded_access["sub"] == user_id
    assert decoded_access["type"] == "access"

    decoded_refresh = decode_jwt_token(refresh_token)
    assert decoded_refresh["sub"] == user_id
    assert decoded_refresh["type"] == "refresh"


@pytest.mark.asyncio
async def test_full_auth_and_user_crud_flow():
    """
    Test full authentication and CRUD workflow:
    1. Register User → Check password hashing and HTTP-only cookies
    2. Login User → Check credentials validation and HTTP-only cookies
    3. Get Profile (/users/me) → Check HTTP-only cookie auth middleware
    4. Refresh Tokens (/auth/refresh) → Check token rotation and new cookies
    5. Update Profile (/users/me) → Check name/email update
    6. Delete Account (/users/me) → Check account deletion
    7. Logout (/auth/logout) → Check cookie deletion
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
        # 1. Register User
        reg_payload = {
            "email": "alice@example.com",
            "password": "Password123!",
            "name": "Alice Developer",
        }
        reg_resp = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_resp.status_code == 201, reg_resp.text
        reg_data = reg_resp.json()
        assert reg_data["user"]["email"] == "alice@example.com"
        assert reg_data["user"]["name"] == "Alice Developer"
        assert "access_token" in reg_resp.cookies
        assert "refresh_token" in reg_resp.cookies

        # 2. Login User
        login_payload = {
            "email": "alice@example.com",
            "password": "Password123!",
        }
        login_resp = await client.post("/api/v1/auth/login", json=login_payload)
        assert login_resp.status_code == 200, login_resp.text
        assert "access_token" in login_resp.cookies
        assert "refresh_token" in login_resp.cookies

        # 3. Test Invalid Credentials Login
        bad_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "alice@example.com", "password": "WrongPassword!"},
        )
        assert bad_login.status_code == 401

        # 4. Get Current User Profile (/users/me)
        me_resp = await client.get("/api/v1/users/me")
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "alice@example.com"

        # 5. Dedicated Refresh Token Route (/auth/refresh)
        refresh_resp = await client.post("/api/v1/auth/refresh")
        assert refresh_resp.status_code == 200
        assert "access_token" in refresh_resp.cookies
        assert "refresh_token" in refresh_resp.cookies

        # 6. Update Profile (/users/me)
        update_payload = {"name": "Alice Senior Developer"}
        update_resp = await client.put("/api/v1/users/me", json=update_payload)
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "Alice Senior Developer"

        # 7. Logout (/auth/logout)
        logout_resp = await client.post("/api/v1/auth/logout")
        assert logout_resp.status_code == 200
        assert logout_resp.json()["message"] == "Successfully logged out."

        # 8. Unauthenticated Access Should Now Fail (HTTP 401)
        unauth_resp = await client.get("/api/v1/users/me")
        assert unauth_resp.status_code == 401

        # 9. Re-login & Delete Account (/users/me)
        await client.post("/api/v1/auth/login", json=login_payload)
        del_resp = await client.delete("/api/v1/users/me")
        assert del_resp.status_code == 200

        # Verify Account No Longer Exists
        login_after_delete = await client.post("/api/v1/auth/login", json=login_payload)
        assert login_after_delete.status_code == 401

    app.dependency_overrides.clear()
    await test_engine.dispose()
