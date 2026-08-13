import { useMutation, useQueryClient } from '@tanstack/react-query';
import authService, { LoginPayload, AuthResponse } from '../../services/authService';
import { AUTH_USER_QUERY_KEY } from '../queries/useAuthUser';
import { useAppDispatch } from '../../store';
import { setUser, logout as logoutAction } from '../../store/slices/authSlice';

export function useLogin() {
  const queryClient = useQueryClient();
  const dispatch = useAppDispatch();

  return useMutation<AuthResponse, Error, LoginPayload>({
    mutationFn: (credentials) => authService.login(credentials),
    onSuccess: (data) => {
      if (data.user) {
        dispatch(setUser(data.user));
      }
      queryClient.invalidateQueries({ queryKey: AUTH_USER_QUERY_KEY });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  const dispatch = useAppDispatch();

  return useMutation<void, Error, void>({
    mutationFn: () => authService.logout(),
    onSuccess: () => {
      dispatch(logoutAction());
      queryClient.clear();
    },
  });
}
