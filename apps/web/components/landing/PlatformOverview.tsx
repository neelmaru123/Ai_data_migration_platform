'use client';

import React from 'react';
import { Check } from 'lucide-react';

export default function PlatformOverview() {
  return (
    <section id="overview" className="py-24 bg-black relative border-t border-sky-400/10 rounded-none overflow-hidden">
      {/* Background Specular Ambient Lights for Sky Blue Frosted Glass Blur */}
      <div className="absolute top-1/2 left-1/4 -translate-y-1/2 w-[500px] h-[300px] bg-sky-400/[0.05] rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute top-1/2 right-1/4 -translate-y-1/2 w-[500px] h-[300px] bg-sky-500/[0.03] rounded-full blur-[140px] pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* 3 Architectural Cards - Sky Blue Frosted Glass */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1 */}
          <div className="p-8 rounded-none bg-gradient-to-b from-sky-400/[0.1] via-sky-400/[0.03] to-sky-400/[0.01] backdrop-blur-3xl border border-sky-400/25 hover:border-sky-400/50 shadow-[0_8px_32px_0_rgba(0,0,0,0.8)] transition-all duration-300 flex flex-col justify-between group">
            <div>
              <div className="text-xs font-mono font-bold text-sky-400 tracking-wider uppercase mb-3">
                01. Schema Translation Engine
              </div>
              <h3 className="text-xl font-bold text-white mb-3 tracking-tight group-hover:text-sky-200 transition-colors">
                Automated Type & Schema Inference
              </h3>
              <p className="text-zinc-400 text-sm leading-relaxed mb-6">
                Analyzes source database definitions and infers target schemas, resolving column mappings and data type conversions into deterministic JSON contracts.
              </p>
            </div>
            <ul className="space-y-2.5 pt-5 border-t border-sky-400/15 text-xs text-zinc-300 font-medium">
              <li className="flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-sky-400" />
                <span>Cross-database type conversion</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-sky-400" />
                <span>Deterministic plan validation</span>
              </li>
            </ul>
          </div>

          {/* Card 2 */}
          <div className="p-8 rounded-none bg-gradient-to-b from-sky-400/[0.1] via-sky-400/[0.03] to-sky-400/[0.01] backdrop-blur-3xl border border-sky-400/25 hover:border-sky-400/50 shadow-[0_8px_32px_0_rgba(0,0,0,0.8)] transition-all duration-300 flex flex-col justify-between group">
            <div>
              <div className="text-xs font-mono font-bold text-sky-400 tracking-wider uppercase mb-3">
                02. Streaming ETL Pipeline
              </div>
              <h3 className="text-xl font-bold text-white mb-3 tracking-tight group-hover:text-sky-200 transition-colors">
                Constant Memory Chunking
              </h3>
              <p className="text-zinc-400 text-sm leading-relaxed mb-6">
                Executes datasets in streaming batch chunks using Polars lazy frames and DuckDB columnar memory buffers, preventing Out-Of-Memory memory spikes.
              </p>
            </div>
            <ul className="space-y-2.5 pt-5 border-t border-sky-400/15 text-xs text-zinc-300 font-medium">
              <li className="flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-sky-400" />
                <span>O(1) memory cursor iterators</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-sky-400" />
                <span>Apache Arrow zero-copy memory</span>
              </li>
            </ul>
          </div>

          {/* Card 3 */}
          <div className="p-8 rounded-none bg-gradient-to-b from-sky-400/[0.1] via-sky-400/[0.03] to-sky-400/[0.01] backdrop-blur-3xl border border-sky-400/25 hover:border-sky-400/50 shadow-[0_8px_32px_0_rgba(0,0,0,0.8)] transition-all duration-300 flex flex-col justify-between group">
            <div>
              <div className="text-xs font-mono font-bold text-sky-400 tracking-wider uppercase mb-3">
                03. Enterprise Security
              </div>
              <h3 className="text-xl font-bold text-white mb-3 tracking-tight group-hover:text-sky-200 transition-colors">
                HTTP-Only Token Rotation
              </h3>
              <p className="text-zinc-400 text-sm leading-relaxed mb-6">
                Built with HTTP-only cookie authentication, automated 401 token refresh queueing, and encrypted credential storage.
              </p>
            </div>
            <ul className="space-y-2.5 pt-5 border-t border-sky-400/15 text-xs text-zinc-300 font-medium">
              <li className="flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-sky-400" />
                <span>Secure HTTP-only JWT cookies</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-sky-400" />
                <span>Encrypted connection strings</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
