'use client';

import React, { useState, useEffect } from 'react';
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

  const status = job.status.toLowerCase();
  const isRunning = status === 'running' || status === 'pending';
  const isCompleted = status === 'completed';
  const isFailed = status === 'failed';

  useEffect(() => {
    if (!isRunning) return;

    const interval = setInterval(async () => {
      try {
        const updated = await executionService.getExecutionDetails(job.id);
        setJob(updated);
        if (onJobUpdated) onJobUpdated(updated);

        if (updated.status === 'completed' || updated.status === 'failed') {
          clearInterval(interval);
        }
      } catch {
        // Polling catch
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [job.id, isRunning, onJobUpdated]);

  const progressPercent = Math.min(100, Math.max(0, job.progress_percent || 0));

  return (
    <div className="p-6 rounded-none bg-black border border-sky-400/40 backdrop-blur-xl space-y-6 shadow-[0_0_25px_rgba(56,189,248,0.15)] font-mono animate-fadeIn">
      {/* Header & Status Pill */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-bold tracking-widest px-2.5 py-0.5 rounded-none uppercase bg-sky-400/10 text-sky-400 border border-sky-400/30">
              AGENT EXECUTION DAEMON
            </span>
            <span
              className={`text-[10px] font-bold tracking-widest px-2.5 py-0.5 rounded-none uppercase border ${
                isCompleted
                  ? 'bg-emerald-400/15 text-emerald-400 border-emerald-400/40'
                  : isFailed
                  ? 'bg-rose-500/15 text-rose-400 border-rose-500/40'
                  : 'bg-sky-400/15 text-sky-400 border-sky-400/40 animate-pulse'
              }`}
            >
              STATUS: {status.toUpperCase()}
            </span>
          </div>
          <h3 className="text-xl font-extrabold text-white uppercase font-sans tracking-wide">
            Live Data Migration Job # {job.id.slice(0, 8)}
          </h3>
        </div>

        <div className="flex items-center gap-6 text-xs text-zinc-400">
          <div>
            Tables Completed: <strong className="text-white">{job.tables_completed || 0} / {job.total_tables || 0}</strong>
          </div>
          <div>
            Rows Migrated: <strong className="text-sky-400">{(job.rows_migrated || 0).toLocaleString()}</strong>
          </div>
        </div>
      </div>

      {/* Animated Progress Bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs font-bold">
          <span className="text-zinc-300 uppercase">
            {job.current_stage || (isRunning ? 'Processing Agent Pipeline...' : 'Job Completed')}
          </span>
          <span className="text-sky-400">{progressPercent}%</span>
        </div>

        <div className="w-full h-3 bg-zinc-950 border border-zinc-800 rounded-none overflow-hidden relative">
          <div
            className={`h-full transition-all duration-500 ${
              isCompleted ? 'bg-emerald-400' : isFailed ? 'bg-rose-500' : 'bg-sky-400'
            }`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Stage Details / Logs Console */}
      {job.stage_details && (
        <div className="p-4 rounded-none bg-zinc-950 border border-zinc-900 text-xs space-y-1">
          <span className="text-[10px] text-zinc-500 font-bold uppercase block mb-1">
            STAGE EXECUTION DETAILS
          </span>
          <pre className="text-sky-400 whitespace-pre-wrap font-mono text-[11px]">
            {JSON.stringify(job.stage_details, null, 2)}
          </pre>
        </div>
      )}

      {/* Error Message if Failed */}
      {isFailed && job.error_message && (
        <div className="p-4 rounded-none bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-mono">
          🚨 <strong>Execution Failure:</strong> {job.error_message}
        </div>
      )}
    </div>
  );
};

export default JobExecutionBanner;
