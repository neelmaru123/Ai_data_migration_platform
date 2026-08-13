"""
Pydantic Schemas for User Module & Authentication
"""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserRegister(BaseModel):
    """Payload to register a new user account."""
    email: EmailStr = Field(..., examples=["user@example.com"])
    password: str = Field(..., min_length=8, examples=["SecurePass123!"])
    name: str = Field(..., min_length=2, max_length=255, examples=["Alice Smith"])


class UserLogin(BaseModel):
    """Payload to authenticate user."""
    email: EmailStr = Field(..., examples=["user@example.com"])
    password: str = Field(..., examples=["SecurePass123!"])


class GoogleAuthRequest(BaseModel):
    """Payload for Google OAuth ID Token verification."""
    id_token: str = Field(..., description="Google OAuth ID Token from client authentication")


class UserUpdate(BaseModel):
    """Payload to update current user profile details."""
    name: Optional[str] = Field(None, min_length=2, max_length=255, examples=["Alice Smith"])
    email: Optional[EmailStr] = Field(None, examples=["newemail@example.com"])
    password: Optional[str] = Field(None, min_length=8, examples=["NewPassword123!"])


class UserResponse(BaseModel):
    """Public user profile data structure."""
    id: uuid.UUID
    email: EmailStr
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Authentication response wrapper."""
    message: str
    user: UserResponse


class MessageResponse(BaseModel):
    """Standard message response structure."""
    message: str
