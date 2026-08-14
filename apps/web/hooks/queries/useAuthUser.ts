import { useQuery } from '@tanstack/react-query';
import authService from '../../services/authService';
import { UserResponse } from '../../types/auth';
import { useAppDispatch } from '../../store';
import { setUser } from '../../store/slices/authSlice';
import { useEffect } from 'react';

export const AUTH_USER_QUERY_KEY = ['authUser'];

export function useAuthUser() {
  const dispatch = useAppDispatch();

  const query = useQuery<UserResponse, Error>({
    queryKey: AUTH_USER_QUERY_KEY,
    queryFn: () => authService.getMe(),
    staleTime: 1000 * 60 * 15, // 15 minutes
    retry: false,
  });

  // Sync current user state into Redux store
  useEffect(() => {
    if (query.data) {
      dispatch(setUser(query.data));
    } else if (query.isError) {
      dispatch(setUser(null));
    }
  }, [query.data, query.isError, dispatch]);

  return query;
}
