import apiClient from './axios';
import {
  UserRegisterPayload,
  UserLoginPayload,
  GoogleAuthRequestPayload,
  UserUpdatePayload,
  UserResponse,
  TokenResponse,
  MessageResponse,
  GoogleLoginUrlResponse,
} from '../types/auth';

export const authService = {
  /**
   * Register a new user account (POST /auth/register)
   */
  async register(payload: UserRegisterPayload): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/auth/register', payload);
    return response.data;
  },

  /**
   * Login user with email & password (POST /auth/login)
   */
  async login(payload: UserLoginPayload): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/auth/login', payload);
    return response.data;
  },

  /**
   * Authenticate via Google OAuth ID Token (POST /auth/google)
   */
  async googleAuth(payload: GoogleAuthRequestPayload): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/auth/google', payload);
    return response.data;
  },

  /**
   * Get Google OAuth consent URL (GET /auth/google/login)
   */
  async getGoogleLoginUrl(): Promise<GoogleLoginUrlResponse> {
    const response = await apiClient.get<GoogleLoginUrlResponse>('/auth/google/login');
    return response.data;
  },

  /**
   * Trigger token refresh rotation via HTTP-only cookie (POST /auth/refresh)
   */
  async refreshToken(): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/auth/refresh');
    return response.data;
  },

  /**
   * Logout user and clear HTTP-only cookies (POST /auth/logout)
   */
  async logout(): Promise<MessageResponse> {
    const response = await apiClient.post<MessageResponse>('/auth/logout');
    return response.data;
  },

  /**
   * Get current authenticated user profile (GET /users/me)
   */
  async getMe(): Promise<UserResponse> {
    const response = await apiClient.get<UserResponse>('/users/me');
    return response.data;
  },

  /**
   * Update profile details for authenticated user (PUT /users/me)
   */
  async updateMe(payload: UserUpdatePayload): Promise<UserResponse> {
    const response = await apiClient.put<UserResponse>('/users/me', payload);
    return response.data;
  },

  /**
   * Delete current logged-in user account (DELETE /users/me)
   */
  async deleteMe(): Promise<MessageResponse> {
    const response = await apiClient.delete<MessageResponse>('/users/me');
    return response.data;
  },
};

export default authService;
