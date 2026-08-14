'use client';

import React, { useState } from 'react';
import authService from '../../services/authService';
import toast from 'react-hot-toast';

interface GoogleAuthButtonProps {
  label?: string;
}

export default function GoogleAuthButton({ label = 'Continue with Google' }: GoogleAuthButtonProps) {
  const [loading, setLoading] = useState(false);

  const handleGoogleClick = async () => {
    try {
      setLoading(true);
      const res = await authService.getGoogleLoginUrl();
      if (res.url) {
        window.location.href = res.url;
      }
    } catch (err: any) {
      setLoading(false);
      toast.error(err.response?.data?.detail || 'Failed to initialize Google Auth');
    }
  };

  return (
    <button
      type="button"
      onClick={handleGoogleClick}
      disabled={loading}
      className="w-full py-3 px-4 rounded-none bg-sky-400/10 hover:bg-sky-400/20 backdrop-blur-xl border border-sky-400/30 hover:border-sky-400/60 text-sky-200 hover:text-white text-xs font-semibold uppercase tracking-wider transition-all duration-200 flex items-center justify-center gap-3 disabled:opacity-50 shadow-md"
    >
      <svg className="w-4 h-4" viewBox="0 0 24 24">
        <path
          fill="#EA4335"
          d="M12 5c1.6 0 3 .6 4.1 1.6l3.1-3.1C17.3 1.7 14.8 1 12 1 7.5 1 3.7 3.6 1.9 7.3l3.7 2.9C6.5 7.3 9 5 12 5z"
        />
        <path
          fill="#4285F4"
          d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.8z"
        />
        <path
          fill="#FBBC05"
          d="M5.6 14.8c-.2-.7-.4-1.5-.4-2.3s.2-1.6.4-2.3L1.9 7.3C.7 9.7 0 10.8 0 12s.7 2.3 1.9 4.7l3.7-1.9z"
        />
        <path
          fill="#34A853"
          d="M12 23c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3 0-5.5-2.3-6.4-5.2L1.9 16c1.8 3.7 5.6 7 10.1 7z"
        />
      </svg>
      <span>{loading ? 'Connecting to Google...' : label}</span>
    </button>
  );
}
