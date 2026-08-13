import { useMutation, useQueryClient } from '@tanstack/react-query';
import authService from '../../services/authService';
import {
  UserRegisterPayload,
  UserLoginPayload,
  GoogleAuthRequestPayload,
  UserUpdatePayload,
  TokenResponse,
  MessageResponse,
  UserResponse,
} from '../../types/auth';
import { AUTH_USER_QUERY_KEY } from '../queries/useAuthUser';
import { useAppDispatch } from '../../store';
import { setUser, logout as logoutAction } from '../../store/slices/authSlice';
import toast from 'react-hot-toast';

/**
 * Register mutation hook (POST /auth/register)
 */
export function useRegister() {
  const queryClient = useQueryClient();
  const dispatch = useAppDispatch();

  return useMutation<TokenResponse, Error, UserRegisterPayload>({
    mutationFn: (payload) => authService.register(payload),
    onSuccess: (data) => {
      dispatch(setUser(data.user));
      queryClient.invalidateQueries({ queryKey: AUTH_USER_QUERY_KEY });
      toast.success(data.message || 'Account created successfully!');
    },
  });
}

/**
 * Login mutation hook (POST /auth/login)
 */
export function useLogin() {
  const queryClient = useQueryClient();
  const dispatch = useAppDispatch();

  return useMutation<TokenResponse, Error, UserLoginPayload>({
    mutationFn: (payload) => authService.login(payload),
    onSuccess: (data) => {
      dispatch(setUser(data.user));
      queryClient.invalidateQueries({ queryKey: AUTH_USER_QUERY_KEY });
      toast.success(data.message || 'Login successful!');
    },
  });
}

/**
 * Google Auth mutation hook (POST /auth/google)
 */
export function useGoogleAuth() {
  const queryClient = useQueryClient();
  const dispatch = useAppDispatch();

  return useMutation<TokenResponse, Error, GoogleAuthRequestPayload>({
    mutationFn: (payload) => authService.googleAuth(payload),
    onSuccess: (data) => {
      dispatch(setUser(data.user));
      queryClient.invalidateQueries({ queryKey: AUTH_USER_QUERY_KEY });
      toast.success(data.message || 'Google authentication successful!');
    },
  });
}

/**
 * Logout mutation hook (POST /auth/logout)
 */
export function useLogout() {
  const queryClient = useQueryClient();
  const dispatch = useAppDispatch();

  return useMutation<MessageResponse, Error, void>({
    mutationFn: () => authService.logout(),
    onSuccess: (data) => {
      dispatch(logoutAction());
      queryClient.clear();
      toast.success(data.message || 'Logged out successfully');
    },
  });
}

/**
 * Update Profile mutation hook (PUT /users/me)
 */
export function useUpdateProfile() {
  const queryClient = useQueryClient();
  const dispatch = useAppDispatch();

  return useMutation<UserResponse, Error, UserUpdatePayload>({
    mutationFn: (payload) => authService.updateMe(payload),
    onSuccess: (updatedUser) => {
      dispatch(setUser(updatedUser));
      queryClient.setQueryData(AUTH_USER_QUERY_KEY, updatedUser);
      toast.success('Profile updated successfully!');
    },
  });
}
