/**
 * TypeScript DTOs matching FastAPI backend Pydantic schemas in apps/api/app/modules/users/users_schemas.py
 */

export interface UserRegisterPayload {
  email: string;
  password: string;
  name: string;
}

export interface UserLoginPayload {
  email: string;
  password: string;
}

export interface GoogleAuthRequestPayload {
  id_token: string;
}

export interface UserUpdatePayload {
  name?: string;
  email?: string;
  password?: string;
}

export interface UserResponse {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  message: string;
  user: UserResponse;
}

export interface MessageResponse {
  message: string;
}

export interface GoogleLoginUrlResponse {
  url: string;
  message: string;
}
