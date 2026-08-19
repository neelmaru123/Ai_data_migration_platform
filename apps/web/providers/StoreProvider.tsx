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
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4500,
            style: {
              background: 'rgba(9, 9, 11, 0.92)',
              color: '#f8fafc',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              borderRadius: '2px',
              padding: '10px 16px',
              fontSize: '12px',
              fontWeight: '500',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              boxShadow: '0 10px 30px -5px rgba(0, 0, 0, 0.8), 0 0 15px rgba(56, 189, 248, 0.15)',
              letterSpacing: '-0.01em',
            },
            success: {
              style: {
                border: '1px solid rgba(56, 189, 248, 0.5)',
                boxShadow: '0 10px 30px -5px rgba(0, 0, 0, 0.8), 0 0 20px rgba(56, 189, 248, 0.25)',
              },
              iconTheme: {
                primary: '#38bdf8',
                secondary: '#09090b',
              },
            },
            error: {
              style: {
                border: '1px solid rgba(239, 68, 68, 0.5)',
                boxShadow: '0 10px 30px -5px rgba(0, 0, 0, 0.8), 0 0 20px rgba(239, 68, 68, 0.25)',
              },
              iconTheme: {
                primary: '#ef4444',
                secondary: '#09090b',
              },
            },
            loading: {
              style: {
                border: '1px solid rgba(56, 189, 248, 0.3)',
              },
              iconTheme: {
                primary: '#38bdf8',
                secondary: '#09090b',
              },
            },
          }}
        />
        {children}
        {process.env.NODE_ENV !== 'production' && (
          <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-right" />
        )}
      </QueryClientProvider>
    </Provider>
  );
}
