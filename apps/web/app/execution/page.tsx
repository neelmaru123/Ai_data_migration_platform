'use client';

import React, { useState, useEffect } from 'react';
import { ExecutionJobResponse } from '../../types/execution';
import executionService from '../../services/executionService';
import JobExecutionBanner from '../../components/plans/JobExecutionBanner';

export default function ExecutionPage() {
  const [executions, setExecutions] = useState<ExecutionJobResponse[]>([]);
  const [selectedJob, setSelectedJob] = useState<ExecutionJobResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchExecutions = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const list = await executionService.listUserExecutions();
      setExecutions(list);
      if (list && list.length > 0) {
        setSelectedJob(list[0]);
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to fetch execution jobs.';
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExecutions();
  }, []);

  const totalMigratedRows = executions.reduce((acc, job) => acc + (job.successful_rows || 0), 0);
  const activeJobsCount = executions.filter((job) => job.status === 'running' || job.status === 'pending').length;
  const completedJobsCount = executions.filter((job) => job.status === 'completed').length;

  return (
    <div className="min-h-screen bg-black text-slate-100 flex flex-col justify-between selection:bg-sky-400 selection:text-black">
      {/* Background Glow */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-96 bg-gradient-to-b from-sky-400/15 via-sky-500/5 to-transparent blur-3xl pointer-events-none -z-10" />

      <main className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 flex-1">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-zinc-800 pb-6">
          <div>
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-none text-[11px] font-mono font-bold uppercase tracking-widest bg-sky-400/10 text-sky-400 border border-sky-400/30 mb-2">
              TARGET DB INSERTION ENGINE
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight sm:text-4xl uppercase font-sans">
              Migration Execution Monitor
            </h1>
            <p className="text-zinc-400 text-xs sm:text-sm max-w-2xl mt-1 leading-relaxed">
              Real-time progression monitor tracking chunked target database insertions, stream throughput, and agent execution logs.
            </p>
          </div>

          <button
            type="button"
            onClick={fetchExecutions}
            className="py-3 px-6 rounded-none bg-zinc-900 hover:bg-zinc-800 text-sky-400 text-xs font-mono font-bold uppercase tracking-wider border border-sky-400/30 transition-colors shadow-lg"
          >
            ↻ Refresh Jobs
          </button>
        </div>

        {/* Global Execution Metrics Overview */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="p-4 rounded-none bg-black border border-zinc-800 space-y-1 shadow-xl">
            <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase block">TOTAL JOBS DISPATCHED</span>
            <span className="text-2xl font-extrabold text-white font-mono">{executions.length}</span>
            <span className="text-[10px] text-zinc-400 block font-mono">Platform execution history</span>
          </div>

          <div className="p-4 rounded-none bg-black border border-zinc-800 space-y-1 shadow-xl">
            <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase block">ACTIVE INSERTS</span>
            <span className="text-2xl font-extrabold text-sky-400 font-mono">{activeJobsCount}</span>
            <span className="text-[10px] text-sky-400/80 block font-mono">Currently streaming</span>
          </div>

          <div className="p-4 rounded-none bg-black border border-zinc-800 space-y-1 shadow-xl">
            <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase block">COMPLETED JOBS</span>
            <span className="text-2xl font-extrabold text-emerald-400 font-mono">{completedJobsCount}</span>
            <span className="text-[10px] text-zinc-400 block font-mono">100% Target verified</span>
          </div>

          <div className="p-4 rounded-none bg-black border border-zinc-800 space-y-1 shadow-xl">
            <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase block">TOTAL TARGET ROWS</span>
            <span className="text-2xl font-extrabold text-sky-400 font-mono">{totalMigratedRows.toLocaleString()}</span>
            <span className="text-[10px] text-zinc-400 block font-mono">Total committed records</span>
          </div>
        </div>

        {/* Selected Job Live Banner */}
        {selectedJob && (
          <div className="space-y-3">
            <div className="text-xs font-mono font-bold text-sky-400 uppercase tracking-wider flex items-center gap-2">
              <span className="w-2 h-2 rounded-none bg-sky-400 inline-block animate-pulse" />
              Active Job Live Progression: {selectedJob.id}
            </div>
            <JobExecutionBanner
              job={selectedJob}
              onJobUpdated={(updated) => {
                setExecutions((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
                if (selectedJob?.id === updated.id) setSelectedJob(updated);
              }}
            />
          </div>
        )}

        {/* Job History List */}
        <div className="space-y-4 font-mono">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <span className="w-2 h-2 rounded-none bg-blue-500 inline-block" />
              All Execution History Jobs
            </h3>
          </div>

          {loading ? (
            <div className="p-12 text-center bg-black border border-zinc-800 text-zinc-400 text-xs">
              Fetching execution jobs...
            </div>
          ) : errorMsg ? (
            <div className="p-8 text-center bg-black border border-rose-500/30 text-rose-400 text-xs">
              {errorMsg}
            </div>
          ) : executions.length === 0 ? (
            <div className="p-12 text-center bg-black border border-zinc-800 text-zinc-400 text-xs">
              No execution jobs dispatched yet. Approve a plan from the Transformation Plan page to trigger a job.
            </div>
          ) : (
            <div className="overflow-x-auto border border-zinc-800 bg-black shadow-xl">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-zinc-800 text-zinc-400 uppercase text-[10px] tracking-wider bg-zinc-950">
                    <th className="p-3.5">Job ID</th>
                    <th className="p-3.5">Plan ID</th>
                    <th className="p-3.5">Status</th>
                    <th className="p-3.5">Insertion Progress</th>
                    <th className="p-3.5">Rows Migrated</th>
                    <th className="p-3.5">Created At</th>
                    <th className="p-3.5 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900">
                  {executions.map((jobItem) => {
                    const isSelected = selectedJob?.id === jobItem.id;
                    const st = (jobItem.status || '').toLowerCase();

                    return (
                      <tr
                        key={jobItem.id}
                        onClick={() => setSelectedJob(jobItem)}
                        className={`cursor-pointer transition-colors ${
                          isSelected ? 'bg-sky-400/10 text-white' : 'hover:bg-zinc-950'
                        }`}
                      >
                        <td className="p-3.5 font-bold text-sky-400">
                          {jobItem.id.slice(0, 8)}...
                        </td>
                        <td className="p-3.5 text-zinc-300">
                          {jobItem.migration_plan_id.slice(0, 8)}...
                        </td>
                        <td className="p-3.5">
                          <span
                            className={`px-2 py-0.5 text-[9px] font-bold uppercase rounded-none border ${
                              st === 'completed'
                                ? 'bg-emerald-400/10 text-emerald-400 border-emerald-400/30'
                                : st === 'failed'
                                ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                                : 'bg-sky-400/10 text-sky-400 border-sky-400/30'
                            }`}
                          >
                            {st}
                          </span>
                        </td>
                        <td className="p-3.5 text-white font-bold">
                          {Math.round(jobItem.progress || 0)}%
                        </td>
                        <td className="p-3.5 text-emerald-400 font-bold">
                          {(jobItem.successful_rows || 0).toLocaleString()} / {(jobItem.total_rows || 0).toLocaleString()}
                        </td>
                        <td className="p-3.5 text-zinc-500 text-[11px]">
                          {new Date(jobItem.created_at).toLocaleString()}
                        </td>
                        <td className="p-3.5 text-right">
                          <a
                            href={`/transformation-plan?planId=${jobItem.migration_plan_id}`}
                            className="py-1 px-3 rounded-none bg-zinc-900 hover:bg-zinc-800 text-sky-400 text-[10px] font-bold uppercase border border-zinc-800 inline-block"
                          >
                            View Plan
                          </a>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
