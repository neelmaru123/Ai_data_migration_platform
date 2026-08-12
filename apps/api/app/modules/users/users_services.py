"""
User Module Database CRUD Service Layer
"""

import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.modules.users.users_models import User
from app.modules.users.users_schemas import UserRegister, UserUpdate


class UserService:
    """Async database operations for User domain entity."""

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        """Fetch user by primary key UUID."""
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """Fetch user by unique email address."""
        stmt = select(User).where(User.email == email.lower().strip())
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def create_user(db: AsyncSession, payload: UserRegister) -> User:
        """Register new user account with bcrypt password hashing."""
        existing = await UserService.get_user_by_email(db, payload.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email address already exists.",
            )

        hashed_pwd = hash_password(payload.password)
        user = User(
            email=payload.email.lower().strip(),
            password_hash=hashed_pwd,
            name=payload.name.strip(),
            is_active=True,
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
        """Validate user credentials against stored bcrypt password hash."""
        user = await UserService.get_user_by_email(db, email)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    async def update_user(db: AsyncSession, user: User, payload: UserUpdate) -> User:
        """Update profile attributes and re-hash password if updated."""
        if payload.email is not None and payload.email.lower().strip() != user.email:
            existing = await UserService.get_user_by_email(db, payload.email)
            if existing and existing.id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This email address is already in use by another account.",
                )
            user.email = payload.email.lower().strip()

        if payload.name is not None:
            user.name = payload.name.strip()

        if payload.password is not None:
            user.password_hash = hash_password(payload.password)

        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def delete_user(db: AsyncSession, user: User) -> None:
        """Delete user account and cascade delete related records."""
        await db.delete(user)
        await db.commit()

    @staticmethod
    async def list_users(db: AsyncSession, skip: int = 0, limit: int = 50) -> List[User]:
        """Fetch paginated list of users."""
        stmt = select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())
