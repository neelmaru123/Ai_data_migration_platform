'use client';

import React from 'react';
import Link from 'next/link';

export default function Footer() {
  return (
    <footer className="bg-slate-950 border-t border-slate-800/80 py-10 text-slate-400 text-xs font-sans">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6 mb-8">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-sm bg-slate-900 border border-slate-700 flex items-center justify-center text-slate-100 font-extrabold text-xs">
              N
            </div>
            <span className="font-bold text-sm text-slate-200 uppercase tracking-tight">
              Nexus<span className="text-indigo-400">Data</span>
            </span>
          </div>

          <nav className="flex items-center gap-6 font-semibold uppercase tracking-wider text-[11px] text-slate-400">
            <a href="#overview" className="hover:text-white transition-colors">
              Architecture
            </a>
            <a href="#features" className="hover:text-white transition-colors">
              Capabilities
            </a>
            <a href="#workflow" className="hover:text-white transition-colors">
              Workflow
            </a>
            <Link href="/login" className="hover:text-white transition-colors">
              Sign In
            </Link>
            <Link href="/register" className="hover:text-white transition-colors">
              Register
            </Link>
          </nav>
        </div>

        <div className="pt-6 border-t border-slate-900 flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px] text-slate-500 font-mono">
          <div>
            &copy; {new Date().getFullYear()} NexusData Platform. All rights reserved.
          </div>
          <div>
            Polars & DuckDB ETL Streaming Engine
          </div>
        </div>
      </div>
    </footer>
  );
}
