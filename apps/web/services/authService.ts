import apiClient from './axios';

export interface LoginPayload {
  email?: string;
  username?: string;
  password?: string;
}

export interface UserProfile {
  id: string;
  email: string;
  name?: string;
  role?: string;
}

export interface AuthResponse {
  message?: string;
  user?: UserProfile;
}

export const authService = {
  async login(credentials: LoginPayload): Promise<AuthResponse> {
    const response = await apiClient.post<AuthResponse>('/auth/login', credentials);
    return response.data;
  },

  async refreshToken(): Promise<void> {
    await apiClient.post('/auth/refresh');
  },

  async logout(): Promise<void> {
    await apiClient.post('/auth/logout');
  },

  async getMe(): Promise<UserProfile> {
    const response = await apiClient.get<UserProfile>('/auth/me');
    return response.data;
  },
};

export default authService;
