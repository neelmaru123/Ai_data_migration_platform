'use client';

import React, { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useLogin } from '../../hooks/mutations/useAuthMutations';
import { UserLoginPayload } from '../../types/auth';
import GoogleAuthButton from './GoogleAuthButton';
import { ArrowRight, Lock, Mail } from 'lucide-react';
import toast from 'react-hot-toast';

export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const loginMutation = useLogin();

  useEffect(() => {
    const errorParam = searchParams.get('error');
    if (errorParam) {
      toast.error(decodeURIComponent(errorParam));
      // Clean up error from URL without refreshing
      window.history.replaceState({}, '', '/login');
    }
  }, [searchParams]);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<UserLoginPayload>({
    mode: 'onTouched',
  });

  const onSubmit = (data: UserLoginPayload) => {
    loginMutation.mutate(data, {
      onSuccess: () => {
        router.push('/');
      },
    });
  };

  return (
    <div className="space-y-4">
      {/* Google Auth Button */}
      <GoogleAuthButton label="Sign In with Google" />

      {/* Or Divider */}
      <div className="relative flex items-center justify-center my-3">
        <div className="w-full border-t border-sky-400/15" />
        <span className="absolute px-3 bg-black text-[10px] font-mono text-zinc-400 uppercase tracking-widest">
          OR WITH EMAIL
        </span>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
        {/* Email Field */}
        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-wider text-zinc-300 mb-1">
            Email Address
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-sky-400">
              <Mail className="w-3.5 h-3.5" />
            </div>
            <input
              type="email"
              placeholder="user@example.com"
              {...register('email', {
                required: 'Email address is required',
                pattern: {
                  value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                  message: 'Please enter a valid email address',
                },
              })}
              className={`w-full pl-9 pr-3 py-2 bg-sky-400/[0.04] backdrop-blur-md border ${
                errors.email ? 'border-red-500' : 'border-sky-400/30 focus:border-sky-400'
              } rounded-none text-xs text-white placeholder-zinc-500 focus:outline-none transition-colors font-sans`}
            />
          </div>
          {errors.email && (
            <p className="mt-0.5 text-[11px] text-red-400 font-mono">{errors.email.message}</p>
          )}
        </div>

        {/* Password Field */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-zinc-300">
              Password
            </label>
          </div>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-sky-400">
              <Lock className="w-3.5 h-3.5" />
            </div>
            <input
              type="password"
              placeholder="••••••••"
              {...register('password', {
                required: 'Password is required',
              })}
              className={`w-full pl-9 pr-3 py-2 bg-sky-400/[0.04] backdrop-blur-md border ${
                errors.password ? 'border-red-500' : 'border-sky-400/30 focus:border-sky-400'
              } rounded-none text-xs text-white placeholder-zinc-500 focus:outline-none transition-colors font-sans`}
            />
          </div>
          {errors.password && (
            <p className="mt-0.5 text-[11px] text-red-400 font-mono">{errors.password.message}</p>
          )}
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loginMutation.isPending}
          className="w-full py-2.5 px-4 rounded-none bg-sky-400 hover:bg-sky-300 text-black text-xs font-bold uppercase tracking-wider transition-colors flex items-center justify-center gap-2 shadow-lg shadow-sky-950/50 disabled:opacity-50 mt-4"
        >
          <span>{loginMutation.isPending ? 'Signing In...' : 'Sign In'}</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </form>

      {/* Switch to Register */}
      <div className="text-center pt-1">
        <p className="text-xs text-zinc-400">
          Don&apos;t have an account?{' '}
          <Link href="/register" className="text-sky-400 hover:text-sky-300 font-semibold underline underline-offset-4">
            Create Account
          </Link>
        </p>
      </div>
    </div>
  );
}
