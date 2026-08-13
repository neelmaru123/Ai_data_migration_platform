'use client';

import React, { useState, useRef } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { Provider } from 'react-redux';
import { Toaster } from 'react-hot-toast';
import { makeStore, AppStore } from '../store';

interface StoreProviderProps {
  children: React.ReactNode;
}

export default function StoreProvider({ children }: StoreProviderProps) {
  const storeRef = useRef<AppStore>();
  if (!storeRef.current) {
    storeRef.current = makeStore();
  }

  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute default stale time
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <Provider store={storeRef.current}>
      <QueryClientProvider client={queryClient}>
        <Toaster position="top-right" toastOptions={{ duration: 4000 }} />
        {children}
        {process.env.NODE_ENV !== 'production' && (
          <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-right" />
        )}
      </QueryClientProvider>
    </Provider>
  );
}
