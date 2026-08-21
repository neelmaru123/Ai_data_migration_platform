'use client';

import React, { useState, useEffect, useRef } from 'react';
import { ExecutionJobResponse } from '../../types/execution';
import executionService from '../../services/executionService';

interface JobExecutionBannerProps {
  job: ExecutionJobResponse;
  onJobUpdated?: (updatedJob: ExecutionJobResponse) => void;
}

export const JobExecutionBanner: React.FC<JobExecutionBannerProps> = ({
  job: initialJob,
  onJobUpdated,
}) => {
  const [job, setJob] = useState<ExecutionJobResponse>(initialJob);
  const [logs, setLogs] = useState<string[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  const status = (job.status || 'pending').toLowerCase();
  const isRunning = status === 'running' || status === 'pending' || status === 'ddl_executing' || status === 'preparing';
  const isCompleted = status === 'completed';
  const isFailed = status === 'failed';

  // Smooth scroll into view when initialized/approved
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, []);

  // Poll job status every 3.0 seconds ONLY while job is active
  useEffect(() => {
    let isSubscribed = true;
    let intervalId: NodeJS.Timeout | null = null;

    const fetchStatus = async () => {
      try {
        const updated = await executionService.getExecutionDetails(job.id);
        if (!isSubscribed) return;

        setJob(updated);
        if (onJobUpdated) onJobUpdated(updated);

        // Append log line if stage changes or new progress
        const logMsg = `[${new Date().toLocaleTimeString()}] Stage: ${updated.current_stage || 'processing'} | Table: ${updated.current_table || 'N/A'} | Inserted: ${updated.successful_rows || 0} / ${updated.total_rows || 0} rows (${Math.round(updated.progress || 0)}%)`;
        
        setLogs((prev) => {
          if (prev.length > 0 && prev[prev.length - 1] === logMsg) return prev;
          return [...prev.slice(-49), logMsg];
        });

        // STOP POLLING IMMEDIATELY WHEN JOB COMPLETS OR FAILS
        const updatedStatus = (updated.status || '').toLowerCase();
        if (updatedStatus === 'completed' || updatedStatus === 'failed' || updatedStatus === 'cancelled') {
          if (intervalId) clearInterval(intervalId);
        }

      } catch {
        // Polling retry
      }
    };

    const currentStatus = (job.status || '').toLowerCase();
    const isJobActive = currentStatus === 'running' || currentStatus === 'pending' || currentStatus === 'ddl_executing' || currentStatus === 'preparing';

    if (!isJobActive) {
      return;
    }

    fetchStatus();
    intervalId = setInterval(fetchStatus, 3000);

    return () => {
      isSubscribed = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, [job.id, job.status, onJobUpdated]);

  const progressPercent = Math.min(100, Math.max(0, Math.round(job.progress || 0)));
  const totalRows = job.total_rows || 0;
  const succRows = job.successful_rows || 0;
  const failRows = job.failed_rows || 0;
  const procRows = job.processed_rows || 0;

  // Pipeline Stepper configuration
  const stages = [
    { key: 'pre_ddl', label: '1. PRE-MIGRATION DDL', desc: 'Target Table Schema Creation' },
    { key: 'data_streaming', label: '2. TARGET DATA INSERTION', desc: 'Chunked ETL Vector Stream' },
    { key: 'post_ddl', label: '3. POST-MIGRATION DDL', desc: 'Foreign Keys & Constraints' },
    { key: 'completed', label: '4. VERIFICATION & SYNC', desc: 'Target Integrity Check' },
  ];

  const getCurrentStepIndex = () => {
    if (isCompleted) return 3;
    if (isFailed) return -1;
    const stage = (job.current_stage || '').toLowerCase();
    if (stage.includes('pre_ddl')) return 0;
    if (stage.includes('streaming') || stage.includes('data')) return 1;
    if (stage.includes('post_ddl')) return 2;
    return 1;
  };

  const currentStep = getCurrentStepIndex();

  return (
    <div
      ref={containerRef}
      className="p-6 sm:p-8 rounded-none bg-black border border-sky-400/40 backdrop-blur-xl space-y-6 shadow-[0_0_35px_rgba(56,189,248,0.15)] font-mono animate-fadeIn"
    >
      {/* Top Banner Header & Status Badges */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <span className="text-[10px] font-bold tracking-widest px-2.5 py-0.5 rounded-none uppercase bg-sky-400/10 text-sky-400 border border-sky-400/30">
              TARGET DB INSERTION DAEMON
            </span>
            <span
              className={`text-[10px] font-bold tracking-widest px-2.5 py-0.5 rounded-none uppercase border ${
                isCompleted
                  ? 'bg-emerald-400/15 text-emerald-400 border-emerald-400/40 shadow-[0_0_12px_rgba(52,211,153,0.3)]'
                  : isFailed
                  ? 'bg-rose-500/15 text-rose-400 border-rose-500/40 shadow-[0_0_12px_rgba(244,63,94,0.3)]'
                  : 'bg-sky-400/15 text-sky-400 border-sky-400/40 animate-pulse'
              }`}
            >
              STATUS: {status.toUpperCase()}
            </span>
          </div>
          <h3 className="text-2xl font-extrabold text-white uppercase font-sans tracking-tight">
            Live Target Database Insertion Stream
          </h3>
          <p className="text-xs text-zinc-400 font-mono mt-0.5">
            Job ID: <span className="text-sky-400">{job.id}</span>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="p-3 rounded-none bg-zinc-950 border border-zinc-800 text-right font-mono">
            <div className="text-[10px] text-zinc-500 uppercase font-bold">INSERTION PROGRESS</div>
            <div className="text-xl font-bold text-sky-400">{progressPercent}%</div>
          </div>
        </div>
      </div>

      {/* Main Animated Progress Bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs font-bold font-mono">
          <span className="text-zinc-300 uppercase flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-none ${
                isCompleted ? 'bg-emerald-400' : isFailed ? 'bg-rose-500' : 'bg-sky-400 animate-ping'
              }`}
            />
            {isCompleted
              ? '✓ Target Database Insertion Completed'
              : isFailed
              ? '🚨 Target Insertion Failed'
              : `Processing Table: ${job.current_table || 'Initializing...'} (${job.current_stage || 'data_streaming'})`}
          </span>
          <span className="text-sky-400 font-extrabold">{progressPercent}%</span>
        </div>

        <div className="w-full h-4 bg-zinc-950 border border-zinc-800 rounded-none overflow-hidden relative p-0.5">
          <div
            className={`h-full transition-all duration-700 ${
              isCompleted
                ? 'bg-gradient-to-r from-emerald-500 to-teal-300 shadow-[0_0_15px_rgba(52,211,153,0.5)]'
                : isFailed
                ? 'bg-rose-500'
                : 'bg-gradient-to-r from-sky-500 via-blue-400 to-sky-300 shadow-[0_0_15px_rgba(56,189,248,0.5)]'
            }`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Real-time Target DB Insertion Metrics Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-none bg-zinc-950 border border-zinc-800 space-y-1">
          <span className="text-[10px] font-bold text-zinc-500 uppercase block">SUCCESSFUL INSERTIONS</span>
          <span className="text-lg sm:text-xl font-extrabold text-emerald-400">{succRows.toLocaleString()}</span>
          <span className="text-[10px] text-zinc-400 block font-mono">Target DB committed</span>
        </div>

        <div className="p-3.5 rounded-none bg-zinc-950 border border-zinc-800 space-y-1">
          <span className="text-[10px] font-bold text-zinc-500 uppercase block">TOTAL TARGET ROWS</span>
          <span className="text-lg sm:text-xl font-extrabold text-white">{(totalRows || succRows).toLocaleString()}</span>
          <span className="text-[10px] text-zinc-400 block font-mono">Expected total</span>
        </div>

        <div className="p-3.5 rounded-none bg-zinc-950 border border-zinc-800 space-y-1">
          <span className="text-[10px] font-bold text-zinc-500 uppercase block">PROCESSED / SKIPPED</span>
          <span className="text-lg sm:text-xl font-extrabold text-sky-400">{procRows.toLocaleString()}</span>
          <span className="text-[10px] text-zinc-400 block font-mono">Deduplicated / processed</span>
        </div>

        <div className="p-3.5 rounded-none bg-zinc-950 border border-zinc-800 space-y-1">
          <span className="text-[10px] font-bold text-zinc-500 uppercase block">FAILED ROWS</span>
          <span className={`text-lg sm:text-xl font-extrabold ${failRows > 0 ? 'text-rose-400' : 'text-zinc-400'}`}>
            {failRows.toLocaleString()}
          </span>
          <span className="text-[10px] text-zinc-400 block font-mono">Schema errors</span>
        </div>
      </div>

      {/* Step-by-Step Pipeline Timeline */}
      <div className="p-4 rounded-none bg-zinc-950 border border-zinc-900 space-y-3">
        <h4 className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-none bg-sky-400" />
          Target Pipeline Stage Stepper
        </h4>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 text-xs font-mono">
          {stages.map((stg, idx) => {
            const isDone = isCompleted || (currentStep > idx);
            const isCurrent = isRunning && currentStep === idx;

            return (
              <div
                key={stg.key}
                className={`p-3 rounded-none border transition-all ${
                  isDone
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                    : isCurrent
                    ? 'bg-sky-400/15 border-sky-400 text-sky-400 shadow-[0_0_12px_rgba(56,189,248,0.2)] animate-pulse'
                    : 'bg-black border-zinc-900 text-zinc-600'
                }`}
              >
                <div className="flex items-center justify-between text-[10px] font-bold uppercase mb-1">
                  <span>{stg.label}</span>
                  <span>{isDone ? '✓' : isCurrent ? '⚡' : '○'}</span>
                </div>
                <div className="text-[11px] font-bold truncate text-white">{stg.desc}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Live Agent Terminal Log Output */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs text-zinc-400 font-bold uppercase">
          <span>Agent Real-Time Execution Log Stream</span>
          <span className="text-[10px] text-sky-400">{logs.length} Log Events</span>
        </div>

        <div className="p-4 rounded-none bg-zinc-950 border border-zinc-900 text-xs font-mono max-h-40 overflow-y-auto space-y-1">
          {logs.length === 0 ? (
            <div className="text-zinc-600 italic">Waiting for initial log events from Docker Agent...</div>
          ) : (
            logs.map((log, lIdx) => (
              <div key={lIdx} className="text-sky-300/90 hover:text-white transition-colors text-[11px]">
                {log}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Execution Error Banner */}
      {isFailed && job.error_message && (
        <div className="p-4 rounded-none bg-rose-500/10 border border-rose-500/40 text-rose-400 text-xs font-mono space-y-1">
          <div className="font-bold uppercase text-rose-300">🚨 Target Insertion Exception Failure</div>
          <p className="whitespace-pre-wrap">{job.error_message}</p>
        </div>
      )}
    </div>
  );
};

export default JobExecutionBanner;
