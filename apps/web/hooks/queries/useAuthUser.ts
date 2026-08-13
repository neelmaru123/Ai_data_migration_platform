import { useQuery } from '@tanstack/react-query';
import authService, { UserProfile } from '../../services/authService';

export const AUTH_USER_QUERY_KEY = ['authUser'];

export function useAuthUser() {
  return useQuery<UserProfile, Error>({
    queryKey: AUTH_USER_QUERY_KEY,
    queryFn: () => authService.getMe(),
    staleTime: 1000 * 60 * 15, // 15 minutes
    retry: false,
  });
}
