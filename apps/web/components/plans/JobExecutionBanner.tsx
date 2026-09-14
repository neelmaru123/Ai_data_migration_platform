'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { ExecutionJobResponse, AIDiagnosisPayload } from '../../types/execution';
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
  const [jobHistory, setJobHistory] = useState<ExecutionJobResponse[]>([]);
  const [isRetrying, setIsRetrying] = useState<boolean>(false);
  const [isDiagnosing, setIsDiagnosing] = useState<boolean>(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Store callback in a ref so the polling useEffect never needs it in its
  // dependency array — eliminates interval restarts caused by parent re-renders.
  const onJobUpdatedRef = useRef(onJobUpdated);
  useEffect(() => {
    onJobUpdatedRef.current = onJobUpdated;
  });

  const status = (job.status || 'queued').toLowerCase();
  const isDryRunCompleted = status === 'dry_run_completed';
  const isRunning =
    status === 'running' ||
    status === 'pending' ||
    status === 'ddl_executing' ||
    status === 'preparing' ||
    status === 'queued';
  const isRealCompleted = status === 'completed';
  const isCompleted = isRealCompleted || isDryRunCompleted;
  const isFailed = status === 'failed';
  const isDryRun = Boolean(job.is_dry_run || isDryRunCompleted);
  const canResume = isFailed && (job.processed_rows || 0) > 0;
  const [isExecutingReal, setIsExecutingReal] = useState<boolean>(false);

  // Fetch job history for plan
  useEffect(() => {
    let isSubscribed = true;
    if (job.migration_plan_id) {
      executionService.listPlanJobs(job.migration_plan_id)
        .then((history) => {
          if (isSubscribed) setJobHistory(history);
        })
        .catch(() => {});
    }
    return () => { isSubscribed = false; };
  }, [job.migration_plan_id, job.id, job.status]);

  // Smooth scroll into view when initialized/approved
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, []);

  // Poll job status every 2.0 seconds ONLY while job is active
  useEffect(() => {
    let isSubscribed = true;
    let intervalId: NodeJS.Timeout | null = null;

    const fetchStatus = async () => {
      try {
        const updated = await executionService.getExecutionDetails(job.id);
        if (!isSubscribed) return;

        setJob(updated);
        // Use the ref so we never need onJobUpdated in the dependency array
        if (onJobUpdatedRef.current) onJobUpdatedRef.current(updated);

        // Append log line if stage changes or new progress
        const totalTarget = (updated.total_rows && updated.total_rows > 0) ? updated.total_rows : (updated.successful_rows || 0);
        const logMsg = `[${new Date().toLocaleTimeString()}] Stage: ${updated.current_stage || 'processing'} | Table: ${updated.current_table || 'N/A'} | Inserted: ${updated.successful_rows || 0} / ${totalTarget} rows (${Math.round(updated.progress || 0)}%)`;

        setLogs((prev) => {
          if (prev.length > 0 && prev[prev.length - 1] === logMsg) return prev;
          return [...prev.slice(-49), logMsg];
        });

        // STOP POLLING IMMEDIATELY WHEN JOB COMPLETES OR FAILS
        const updatedStatus = (updated.status || '').toLowerCase();
        if (
          updatedStatus === 'completed' ||
          updatedStatus === 'dry_run_completed' ||
          updatedStatus === 'failed' ||
          updatedStatus === 'cancelled'
        ) {
          if (intervalId) clearInterval(intervalId);
        }

      } catch {
        // Polling retry
      }
    };

    const currentStatus = (job.status || '').toLowerCase();
    const isJobActive = currentStatus === 'running' || currentStatus === 'pending' || currentStatus === 'ddl_executing' || currentStatus === 'preparing' || currentStatus === 'queued';

    if (!isJobActive) {
      return;
    }

    fetchStatus();
    intervalId = setInterval(fetchStatus, 2000);

    return () => {
      isSubscribed = false;
      if (intervalId) clearInterval(intervalId);
    };
  // NOTE: onJobUpdated intentionally omitted — stored in a ref above to prevent
  // the interval from restarting when the parent passes a new function reference.
  }, [job.id, job.status]);

  // Handle Execute For Real after Dry Run Simulation
  const handleExecuteForReal = async () => {
    if (isExecutingReal || !job.migration_plan_id) return;
    setIsExecutingReal(true);
    try {
      const newJob = await executionService.startPlanExecution(job.migration_plan_id, { is_dry_run: false });
      setJob(newJob);
      setLogs([`[${new Date().toLocaleTimeString()}] Real migration dispatched to Docker Agent: ${newJob.id}`]);
      toast.success('Real migration job queued on Docker Agent! Data will be written to target DB.');
      if (onJobUpdated) onJobUpdated(newJob);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Failed to start real migration.';
      toast.error(`Execution Error: ${detail}`);
    } finally {
      setIsExecutingReal(false);
    }
  };

  // Handle Retry or Resume Execution Job
  const handleRetryJob = async () => {
    if (isRetrying || !job.migration_plan_id) return;
    setIsRetrying(true);
    try {
      const newJob = await executionService.startPlanExecution(job.migration_plan_id, {
        is_dry_run: Boolean(job.is_dry_run),
      });
      setJob(newJob);
      const actionName = canResume ? 'Resumed' : 'Re-triggered';
      setLogs([`[${new Date().toLocaleTimeString()}] ${actionName} migration job run: ${newJob.id}`]);
      toast.success(
        canResume
          ? 'Migration resumed! Checkpoints reused from last processed record.'
          : 'Migration job retried! New run queued for Docker Agent.'
      );
      if (onJobUpdated) onJobUpdated(newJob);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || (canResume ? 'Failed to resume job.' : 'Failed to retry job.');
      if (err?.response?.status === 503) {
        toast.error(`Agent Offline Warning: ${detail}`, { duration: 8000 });
      } else {
        toast.error(`${canResume ? 'Resume' : 'Retry'} Error: ${detail}`);
      }
    } finally {
      setIsRetrying(false);
    }
  };

  // Handle AI Error Diagnosis Request
  const handleTriggerDiagnosis = async () => {
    if (isDiagnosing || !job.id) return;
    setIsDiagnosing(true);
    try {
      const updated = await executionService.diagnoseJobFailure(job.id);
      setJob(updated);
      toast.success('AI Failure Diagnosis completed!');
      if (onJobUpdated) onJobUpdated(updated);
    } catch (err: any) {
      toast.error(`Diagnosis Error: ${err.message || 'Failed to diagnose job.'}`);
    } finally {
      setIsDiagnosing(false);
    }
  };

  const progressPercent = Math.min(100, Math.max(0, Math.round(job.progress || 0)));
  const totalRows = job.total_rows || 0;
  const succRows = job.successful_rows || 0;
  const failRows = job.failed_rows || 0;
  const procRows = job.processed_rows || 0;
  const diagnosis = job.ai_diagnosis;

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
                isDryRunCompleted
                  ? 'bg-amber-400/20 text-amber-300 border-amber-400/50 shadow-[0_0_12px_rgba(251,191,36,0.3)]'
                  : isCompleted
                  ? 'bg-emerald-400/15 text-emerald-400 border-emerald-400/40 shadow-[0_0_12px_rgba(52,211,153,0.3)]'
                  : isFailed
                  ? 'bg-rose-500/15 text-rose-400 border-rose-500/40 shadow-[0_0_12px_rgba(244,63,94,0.3)]'
                  : 'bg-sky-400/15 text-sky-400 border-sky-400/40 animate-pulse'
              }`}
            >
              STATUS: {status.replace('_', ' ').toUpperCase()}
            </span>

            {/* Run Selector Dropdown */}
            {jobHistory.length > 1 && (
              <select
                value={job.id}
                onChange={async (e) => {
                  const selectedId = e.target.value;
                  const selectedJob = jobHistory.find((j) => j.id === selectedId);
                  if (selectedJob) {
                    setJob(selectedJob);
                    if (onJobUpdated) onJobUpdated(selectedJob);
                  }
                }}
                className="px-2 py-0.5 bg-zinc-900 border border-zinc-700 text-sky-400 text-[10px] font-bold uppercase rounded-none focus:outline-none"
              >
                {jobHistory.map((hJob: ExecutionJobResponse, idx: number) => (
                  <option key={hJob.id} value={hJob.id}>
                    Run #{jobHistory.length - idx} ({hJob.status.toUpperCase()} - {Math.round(hJob.progress)}%)
                  </option>
                ))}
              </select>
            )}
          </div>
          <h3 className="text-2xl font-extrabold text-white uppercase font-sans tracking-tight">
            {isDryRun ? 'Target Database Migration Dry Run Simulation' : 'Live Target Database Insertion Stream'}
          </h3>
          <p className="text-xs text-zinc-400 font-mono mt-0.5">
            Job ID: <span className="text-sky-400">{job.id}</span> {isDryRun && <span className="text-amber-400 ml-2">[DRY RUN ACTIVE]</span>}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Execute For Real Secondary Button */}
          {isDryRun && (
            <button
              type="button"
              onClick={handleExecuteForReal}
              disabled={isExecutingReal}
              className="py-2.5 px-4 rounded-none bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold uppercase tracking-wider border border-emerald-400 shadow-md transition-all font-mono"
            >
              {isExecutingReal ? 'Queuing Real Migration...' : '⚡ EXECUTE FOR REAL'}
            </button>
          )}

          {/* Completed Job: Offer "Create New Migration" */}
          {isRealCompleted && (
            <Link
              href="/profiling"
              className="py-2.5 px-4 rounded-none bg-sky-400 hover:bg-sky-300 text-black text-xs font-bold uppercase tracking-wider border border-sky-400 shadow-md transition-all font-mono inline-flex items-center gap-1.5"
            >
              + CREATE NEW MIGRATION
            </Link>
          )}

          {/* Active Retry / Resume Button for Failed Jobs */}
          {isFailed && (
            <button
              type="button"
              onClick={handleRetryJob}
              disabled={isRetrying}
              title={
                canResume
                  ? `Checkpoints will be reused: resumes execution from ${procRows.toLocaleString()} processed rows.`
                  : 'Retries migration from the beginning.'
              }
              className="py-2.5 px-4 rounded-none bg-sky-400 hover:bg-sky-300 text-black text-xs font-bold uppercase tracking-wider border border-sky-400 shadow-md transition-all font-mono"
            >
              {isRetrying
                ? canResume ? 'Resuming...' : 'Queuing Retry...'
                : canResume
                ? isDryRun ? '⚡ RESUME DRY RUN' : '⚡ RESUME'
                : isDryRun ? '⚡ RETRY DRY RUN' : '⚡ RETRY MIGRATION JOB'}
            </button>
          )}

          {/* Completed Job: Disabled Retry with Tooltip Explaining Checkpoints Reused / Finalized */}
          {isRealCompleted && (
            <button
              type="button"
              disabled={true}
              title="Checkpoints will be reused when the job is completed. Create a new migration instead."
              className="py-2.5 px-4 rounded-none bg-zinc-900 text-zinc-600 text-xs font-bold uppercase tracking-wider border border-zinc-800 cursor-not-allowed font-mono opacity-60"
            >
              ⚡ RETRY (DISABLED)
            </button>
          )}

          {/* Full Monitor Link */}
          <Link
            href={`/execution?jobId=${job.id}`}
            className="py-2.5 px-4 rounded-none bg-zinc-900 hover:bg-zinc-800 text-sky-400 text-xs font-bold uppercase tracking-wider border border-sky-400/40 transition-colors font-mono"
          >
            [ 🖥️ OPEN LIVE MONITOR ]
          </Link>

          <div className="p-3 rounded-none bg-zinc-950 border border-zinc-800 text-right font-mono">
            <div className="text-[10px] text-zinc-500 uppercase font-bold">
              {isDryRun ? 'SIMULATION PROGRESS' : 'INSERTION PROGRESS'}
            </div>
            <div className="text-xl font-bold text-sky-400">{progressPercent}%</div>
          </div>
        </div>
      </div>

      {/* DRY RUN -- NO DATA WAS WRITTEN BANNER */}
      {isDryRun && (
        <div className="p-5 bg-amber-950/40 border border-amber-500/70 text-amber-300 font-mono text-xs space-y-3 shadow-[0_0_20px_rgba(251,191,36,0.15)] animate-fadeIn">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 font-bold">
            <span className="flex items-center gap-2 text-amber-400 uppercase text-xs tracking-wider">
              <span className="w-2.5 h-2.5 bg-amber-400 rounded-none animate-pulse" />
              DRY RUN SIMULATION -- NO DATA WAS WRITTEN TO TARGET DB
            </span>
            {isDryRunCompleted && (
              <span className="text-[9px] px-2 py-0.5 bg-amber-400 text-black uppercase font-bold tracking-wider">
                SIMULATION VERIFIED ✓
              </span>
            )}
          </div>
          <p className="text-[11px] text-zinc-300 font-sans leading-relaxed">
            All source data extractions, AST column mappings, type coercions, and multi-source merge deduplications were executed on real source chunks. Destination DDL schema modifications and database write operations were safely bypassed.
          </p>
          <div className="pt-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-t border-amber-500/30">
            <span className="text-[11px] text-amber-200/90 font-mono">
              Ready to persist rows into the destination target database?
            </span>
            <button
              type="button"
              onClick={handleExecuteForReal}
              disabled={isExecutingReal}
              className="py-2 px-4 rounded-none bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold uppercase tracking-wider font-mono shadow-md whitespace-nowrap"
            >
              {isExecutingReal ? 'Starting Real Run...' : '⚡ Execute For Real'}
            </button>
          </div>
        </div>
      )}

      {/* Target Tables With Existing Data Advisory Warning Banner */}
      {job.target_tables_with_existing_data && job.target_tables_with_existing_data.length > 0 && (
        <div className="p-4 bg-amber-950/40 border border-amber-500/50 text-amber-300 font-mono text-xs space-y-2 animate-fadeIn">
          <div className="flex items-center justify-between font-bold uppercase">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 bg-amber-400 animate-pulse rounded-none" />
              ⚠️ Notice: Target Tables Contain Existing Data
            </span>
            <span className="text-[10px] text-amber-400/80">
              {job.target_tables_with_existing_data.length} Affected Table(s)
            </span>
          </div>
          <p className="text-[11px] text-zinc-300 font-sans leading-relaxed">
            The target database metadata snapshot indicates destination tables already contain data. Incoming rows will be appended according to your plan's primary key conflict resolution policy.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            {job.target_tables_with_existing_data.map((tbl, idx) => (
              <span
                key={idx}
                className="px-2.5 py-1 bg-black/60 border border-amber-500/40 text-amber-300 text-[10px] font-mono"
              >
                <strong className="text-white">{tbl.table_name}</strong>: {tbl.existing_row_count.toLocaleString()} existing rows
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Main Animated Progress Bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs font-bold font-mono">
          <span className="text-zinc-300 uppercase flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-none ${isCompleted ? 'bg-emerald-400' : isFailed ? 'bg-rose-500' : 'bg-sky-400 animate-ping'
                }`}
            />
            {isDryRunCompleted
              ? '✓ Dry Run Simulation Completed (No Data Was Written)'
              : isCompleted
              ? '✓ Target Database Insertion Completed'
              : isFailed
              ? '🚨 Target Insertion Failed'
              : `Processing Table: ${job.current_table || 'Initializing...'} (${job.current_stage || 'data_streaming'})`}
          </span>
          <span className="text-sky-400 font-extrabold">{progressPercent}%</span>
        </div>

        <div className="w-full h-4 bg-zinc-950 border border-zinc-800 rounded-none overflow-hidden relative p-0.5">
          <div
            className={`h-full transition-all duration-700 ${isCompleted
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
          <span className="text-[10px] font-bold text-zinc-500 uppercase block">
            {isDryRun ? 'SIMULATED / VALID ROWS' : 'SUCCESSFUL INSERTIONS'}
          </span>
          <span className="text-lg sm:text-xl font-extrabold text-emerald-400">{succRows.toLocaleString()}</span>
          <span className="text-[10px] text-zinc-400 block font-mono">
            {isDryRun ? 'No rows written to DB' : 'Target DB committed'}
          </span>
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
                className={`p-3 rounded-none border transition-all ${isDone
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

      {/* AI Error Diagnosis & Remediation Card (Failed State) */}
      {isFailed && (
        <div className="p-5 rounded-none bg-rose-950/30 border border-rose-500/50 space-y-4 text-xs font-mono shadow-[0_0_25px_rgba(244,63,94,0.15)]">
          <div className="flex items-center justify-between border-b border-rose-500/30 pb-3 font-sans">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-rose-500 animate-ping rounded-none" />
              <h4 className="text-sm font-extrabold text-rose-300 uppercase tracking-wider">
                🤖 AI Execution Failure Diagnosis & Self-Healing Guide
              </h4>
            </div>
            {diagnosis?.root_cause_category && (
              <span className="px-2.5 py-0.5 text-[10px] font-mono font-bold uppercase bg-rose-500/20 text-rose-300 border border-rose-500/40">
                {diagnosis.root_cause_category}
              </span>
            )}
          </div>

          {/* Diagnosis Plain English Summary */}
          {diagnosis?.summary ? (
            <div className="text-zinc-200 text-xs font-sans leading-relaxed">
              <strong className="text-rose-400 uppercase font-mono mr-2 font-bold">Explanation:</strong>
              {diagnosis.summary}
            </div>
          ) : (
            <div className="text-rose-400 text-xs leading-relaxed font-sans">
              <strong className="uppercase font-mono mr-2 font-bold">Raw Error Trace:</strong>
              {job.error_message || 'Execution error encountered during ETL streaming.'}
            </div>
          )}

          {/* Remediation Steps */}
          {diagnosis?.fix_steps && diagnosis.fix_steps.length > 0 && (
            <div className="space-y-1.5 p-3 bg-black/60 border border-rose-500/30">
              <span className="text-[10px] font-bold text-sky-400 uppercase tracking-wider block">
                🛠️ Step-by-Step Remediation Actions:
              </span>
              <ul className="list-disc list-inside text-zinc-300 text-[11px] space-y-1">
                {diagnosis.fix_steps.map((step: string, sIdx: number) => (
                  <li key={sIdx}>{step}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Copyable Fix Command (With Password Placeholders) */}
          {diagnosis?.copyable_fix_command && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-[10px] font-bold text-amber-400 uppercase">
                <span>📋 Copyable Container Fix Command (Password Placeholders Retained):</span>
                <button
                  type="button"
                  onClick={() => {
                    navigator.clipboard.writeText(diagnosis.copyable_fix_command || '');
                    toast.success('Remediation command copied to clipboard!');
                  }}
                  className="px-2 py-0.5 bg-amber-400/10 hover:bg-amber-400/20 text-amber-300 border border-amber-400/30 uppercase text-[9px] font-bold"
                >
                  Copy Command
                </button>
              </div>
              <pre className="p-3 bg-zinc-950 border border-zinc-800 text-amber-300/90 text-[11px] font-mono whitespace-pre-wrap overflow-x-auto">
                {diagnosis.copyable_fix_command}
              </pre>
            </div>
          )}

          {/* Trigger Diagnosis Manual Button if missing */}
          {!diagnosis && (
            <button
              type="button"
              onClick={handleTriggerDiagnosis}
              disabled={isDiagnosing}
              className="py-2 px-4 bg-rose-500 hover:bg-rose-400 text-black text-xs font-bold uppercase tracking-wider border border-rose-500 font-mono transition-colors"
            >
              {isDiagnosing ? 'Analyzing Error with AI...' : '🤖 Synthesize AI Diagnosis'}
            </button>
          )}
        </div>
      )}

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
            logs.map((log: string, lIdx: number) => (
              <div key={lIdx} className="text-sky-300/90 hover:text-white transition-colors text-[11px]">
                {log}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default JobExecutionBanner;
