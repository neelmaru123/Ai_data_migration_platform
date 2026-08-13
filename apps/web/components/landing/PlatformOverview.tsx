'use client';

import React from 'react';
import { Check } from 'lucide-react';

export default function PlatformOverview() {
  return (
    <section id="overview" className="py-20 bg-slate-950 relative border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* 3 Main Architectural Cards - Solid Dark Shades */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1: Schema Translation */}
          <div className="p-7 rounded-sm bg-slate-900 border border-slate-800 hover:border-indigo-600/40 transition-colors flex flex-col justify-between">
            <div>
              <div className="text-xs font-mono font-bold text-indigo-400 tracking-wider uppercase mb-3">
                01. Schema Translation Engine
              </div>
              <h3 className="text-xl font-bold text-slate-100 mb-3">
                Automated Type & Schema Inference
              </h3>
              <p className="text-slate-400 text-sm leading-relaxed mb-6">
                Analyzes source database definitions and infers target schemas, resolving column mappings and data type conversions into deterministic JSON contracts.
              </p>
            </div>
            <ul className="space-y-2.5 pt-5 border-t border-slate-800 text-xs text-slate-300 font-medium">
              <li className="flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-indigo-400" />
                <span>Cross-database type conversion</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-indigo-400" />
                <span>Deterministic plan validation</span>
              </li>
            </ul>
          </div>

          {/* Card 2: Streaming Engine */}
          <div className="p-7 rounded-sm bg-slate-900 border border-slate-800 hover:border-blue-600/40 transition-colors flex flex-col justify-between">
            <div>
              <div className="text-xs font-mono font-bold text-blue-400 tracking-wider uppercase mb-3">
                02. Streaming ETL Pipeline
              </div>
              <h3 className="text-xl font-bold text-slate-100 mb-3">
                Constant Memory Chunking
              </h3>
              <p className="text-slate-400 text-sm leading-relaxed mb-6">
                Executes datasets in streaming batch chunks using Polars lazy frames and DuckDB columnar memory buffers, preventing Out-Of-Memory memory spikes.
              </p>
            </div>
            <ul className="space-y-2.5 pt-5 border-t border-slate-800 text-xs text-slate-300 font-medium">
              <li className="flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-blue-400" />
                <span>O(1) memory cursor iterators</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-blue-400" />
                <span>Apache Arrow zero-copy memory</span>
              </li>
            </ul>
          </div>

          {/* Card 3: Security & Session */}
          <div className="p-7 rounded-sm bg-slate-900 border border-slate-800 hover:border-purple-600/40 transition-colors flex flex-col justify-between">
            <div>
              <div className="text-xs font-mono font-bold text-purple-400 tracking-wider uppercase mb-3">
                03. Enterprise Security
              </div>
              <h3 className="text-xl font-bold text-slate-100 mb-3">
                HTTP-Only Token Rotation
              </h3>
              <p className="text-slate-400 text-sm leading-relaxed mb-6">
                Built with HTTP-only cookie authentication, automated 401 token refresh queueing, and encrypted credential storage.
              </p>
            </div>
            <ul className="space-y-2.5 pt-5 border-t border-slate-800 text-xs text-slate-300 font-medium">
              <li className="flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-purple-400" />
                <span>Secure HTTP-only JWT cookies</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-purple-400" />
                <span>Encrypted connection strings</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
