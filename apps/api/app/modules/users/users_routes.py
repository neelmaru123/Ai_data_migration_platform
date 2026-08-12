"""
FastAPI Routes for User Domain & Authentication System
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jwt import PyJWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
)
from app.modules.users.users_dependencies import (
    get_current_active_user,
    get_current_user,
)
from app.modules.users.users_models import User
from app.modules.users.users_schemas import (
    MessageResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)
from app.modules.users.users_services import UserService

router = APIRouter(tags=["Authentication & Users"])


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Helper to set HTTP-only access and refresh token cookies."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.COOKIE_SECURE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.COOKIE_SECURE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Helper to clear HTTP-only authentication cookies."""
    response.delete_cookie(key="access_token", path="/", domain=settings.COOKIE_DOMAIN)
    response.delete_cookie(key="refresh_token", path="/", domain=settings.COOKIE_DOMAIN)


# -----------------------------------------------------------------------------
# AUTHENTICATION ROUTES
# -----------------------------------------------------------------------------

@router.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register_user(
    payload: UserRegister,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user account, hash the password, issue access (15 min) and
    refresh (7 day) tokens, and attach them via HTTP-only cookies.
    """
    user = await UserService.create_user(db, payload)

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    _set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(
        message="User account created successfully.",
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Login user and issue HTTP-only cookies",
)
async def login_user(
    payload: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate user credentials, generate 15-minute access token and 7-day
    refresh token, and set HTTP-only cookies.
    """
    user = await UserService.authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated.",
        )

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    _set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(
        message="Login successful.",
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/auth/logout",
    response_model=MessageResponse,
    summary="Logout user and clear HTTP-only cookies",
)
async def logout_user(response: Response):
    """Clear authentication cookies."""
    _clear_auth_cookies(response)
    return MessageResponse(message="Successfully logged out.")


@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    summary="Generate new access and refresh tokens (Token Rotation)",
)
async def refresh_tokens(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Dedicated Token Refresh Endpoint.
    Reads `refresh_token` from HTTP-only cookie, validates token type == 'refresh',
    generates a NEW access token (15 mins) and NEW refresh token (7 days),
    and updates HTTP-only cookies (Token Rotation).
    """
    token = request.cookies.get("refresh_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing from HTTP-only cookie.",
        )

    try:
        payload = decode_jwt_token(token)
        user_id_str: Optional[str] = payload.get("sub")
        token_type: Optional[str] = payload.get("type")

        if not user_id_str or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token payload.",
            )

        user_id = uuid.UUID(user_id_str)
    except (PyJWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token. Please log in again.",
        )

    user = await UserService.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer active or valid.",
        )

    # Token Rotation: Issue new access token AND new refresh token
    new_access_token = create_access_token(subject=user.id)
    new_refresh_token = create_refresh_token(subject=user.id)

    _set_auth_cookies(response, new_access_token, new_refresh_token)

    return TokenResponse(
        message="Tokens refreshed successfully.",
        user=UserResponse.model_validate(user),
    )


# -----------------------------------------------------------------------------
# USER PROFILE & CRUD ROUTES
# -----------------------------------------------------------------------------

@router.get(
    "/users/me",
    response_model=UserResponse,
    summary="Get current logged-in user profile",
)
async def get_my_profile(current_user: User = Depends(get_current_active_user)):
    """Fetch profile of currently authenticated user."""
    return UserResponse.model_validate(current_user)


@router.put(
    "/users/me",
    response_model=UserResponse,
    summary="Update current logged-in user profile",
)
async def update_my_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update profile details (name, email, password) for authenticated user."""
    updated_user = await UserService.update_user(db, current_user, payload)
    return UserResponse.model_validate(updated_user)


@router.delete(
    "/users/me",
    response_model=MessageResponse,
    summary="Delete current logged-in user account",
)
async def delete_my_account(
    response: Response,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete authenticated user account and clear authentication cookies."""
    await UserService.delete_user(db, current_user)
    _clear_auth_cookies(response)
    return MessageResponse(message="Account deleted successfully.")


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Get user profile by UUID",
)
async def get_user_by_id(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch user profile by UUID (Requires authentication)."""
    user = await UserService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' not found.",
        )
    return UserResponse.model_validate(user)


@router.get(
    "/users",
    response_model=List[UserResponse],
    summary="List all users (Paginated)",
)
async def list_users(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List registered users with pagination (Requires authentication)."""
    users = await UserService.list_users(db, skip=skip, limit=limit)
    return [UserResponse.model_validate(u) for u in users]
