'use client';

import React from 'react';
import Link from 'next/link';
import SplineHeroBackground from '../landing/SplineHeroBackground';
import { ArrowLeft } from 'lucide-react';

interface AuthLayoutProps {
  children: React.ReactNode;
  title: string;
  subtitle: string;
  sceneUrl?: string;
}

export default function AuthLayout({
  children,
  title,
  subtitle,
  sceneUrl = 'https://my.spline.design/flow-vD4AAB4End71ev0QfMLT00qI/',
}: AuthLayoutProps) {
  return (
    <div className="h-screen max-h-screen w-full bg-black font-sans text-slate-100 grid grid-cols-1 lg:grid-cols-2 overflow-hidden rounded-none">
      {/* Left Column (50% on lg): Full-height 3D Spline Canvas */}
      <div className="relative hidden lg:block w-full h-full bg-black border-r border-sky-400/10 overflow-hidden">
        <SplineHeroBackground sceneUrl={sceneUrl} interactive={false} />
      </div>

      {/* Right Column (50% on lg): Non-Scrollable 100vh Form Container */}
      <div className="relative flex flex-col justify-between p-4 sm:p-8 lg:p-10 bg-black h-screen max-h-screen overflow-hidden">
        {/* Specular Ambient Glow */}
        <div className="absolute top-1/2 right-1/4 -translate-y-1/2 w-[400px] h-[300px] bg-sky-400/[0.04] rounded-full blur-[140px] pointer-events-none" />

        {/* Top Header */}
        <div className="flex items-center justify-between mb-4 relative z-10 shrink-0">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-xs font-mono font-semibold uppercase tracking-wider text-zinc-400 hover:text-sky-400 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Home</span>
          </Link>

          <Link href="/" className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-none bg-sky-950/80 backdrop-blur-xl border border-sky-400/40 flex items-center justify-center text-sky-400 font-extrabold text-xs">
              M
            </div>
            <span className="font-bold text-sm tracking-tight text-white uppercase">
              Migra<span className="text-sky-400">flow</span>
            </span>
          </Link>
        </div>

        {/* Center Content Box */}
        <div className="w-full max-w-md mx-auto my-auto py-6 px-6 sm:px-8 bg-gradient-to-b from-sky-400/[0.1] via-sky-400/[0.03] to-sky-400/[0.01] backdrop-blur-3xl border border-sky-400/25 shadow-[0_8px_32px_0_rgba(0,0,0,0.8)] rounded-none relative z-10 shrink-0">
          <div className="mb-5">
            <h1 className="text-xl sm:text-2xl font-extrabold text-white tracking-tight mb-1">
              {title}
            </h1>
            <p className="text-zinc-400 text-xs leading-relaxed">
              {subtitle}
            </p>
          </div>

          {/* Form Content */}
          {children}
        </div>

        {/* Bottom Footer */}
        <div className="mt-4 pt-3 border-t border-sky-400/10 text-center text-xs font-mono text-zinc-500 relative z-10 shrink-0">
          &copy; {new Date().getFullYear()} Migraflow. Secure HTTP-Only Sessions.
        </div>
      </div>
    </div>
  );
}
