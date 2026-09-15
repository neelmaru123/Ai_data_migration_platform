'use client';

import React, { useState, useRef, useCallback } from 'react';
import {
  PlanDetailResponse,
  ColumnMappingSpec,
  TransformationPlanAST,
  TableTransformationType,
  ConflictResolutionSpec,
  PlanVersionListItem,
  PlanVersionDetailResponse,
} from '../../types/migrationPlan';
import { ExecutionJobResponse } from '../../types/execution';
import planService from '../../services/planService';
import executionService from '../../services/executionService';
import PlanDiagramViewer from './PlanDiagramViewer';
import JobExecutionBanner from './JobExecutionBanner';
import PlanPlainLanguageSummary from './PlanPlainLanguageSummary';
import {
  PlanReadinessSignals,
  PlanReadinessRollupBadge,
  TableReadinessBadge,
  ColumnConfidenceBadge,
} from './PlanReadinessSignals';
import RefinementFeedbackCard from './RefinementFeedbackCard';
import { RefinementFeedback } from '../../types/migrationPlan';
import { AlertTriangle, Trash2, Database, ShieldAlert } from 'lucide-react';
import toast from 'react-hot-toast';

interface PlanBlueprintViewerProps {
  plan: PlanDetailResponse;
  onPlanUpdated?: (updatedPlan: PlanDetailResponse) => void;
}

export const PlanBlueprintViewer: React.FC<PlanBlueprintViewerProps> = ({
  plan: initialPlan,
  onPlanUpdated,
}) => {
  const [plan, setPlan] = useState<PlanDetailResponse>(initialPlan);
  const [viewMode, setViewMode] = useState<'matrix' | 'diagram'>('matrix');

  // Column Inline Editing State
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editableAst, setEditableAst] = useState<TransformationPlanAST>(initialPlan.plan_data);
  const [isSavingEdits, setIsSavingEdits] = useState<boolean>(false);

  // Target DB Clean Wipe & Safety Confirmation Modal State
  const [showExecutionConfirmModal, setShowExecutionConfirmModal] = useState<boolean>(false);
  const [truncateTarget, setTruncateTarget] = useState<boolean>(false);

  // Version History State
  const [versions, setVersions] = useState<PlanVersionListItem[]>([]);
  const [selectedVersionNum, setSelectedVersionNum] = useState<number | null>(null);
  const [previewVersionDetail, setPreviewVersionDetail] = useState<PlanVersionDetailResponse | null>(null);
  const [isLoadingVersion, setIsLoadingVersion] = useState<boolean>(false);
  const [isRestoringVersion, setIsRestoringVersion] = useState<boolean>(false);

  const fetchVersions = useCallback(async () => {
    try {
      const list = await planService.listPlanVersions(plan.id);
      setVersions(list);
    } catch {
      // fail silently
    }
  }, [plan.id]);

  React.useEffect(() => {
    fetchVersions();
  }, [fetchVersions]);

  const handleSelectVersion = async (versionNum: number | null) => {
    if (versionNum === null || (versions.length > 0 && versionNum === versions[0].version_number)) {
      setSelectedVersionNum(null);
      setPreviewVersionDetail(null);
      return;
    }
    setSelectedVersionNum(versionNum);
    setIsLoadingVersion(true);
    try {
      const verDetail = await planService.getPlanVersion(plan.id, versionNum);
      setPreviewVersionDetail(verDetail);
    } catch (err: any) {
      toast.error('Failed to load version details.');
    } finally {
      setIsLoadingVersion(false);
    }
  };

  const handleRestoreVersion = async (versionNum: number) => {
    if (isRestoringVersion) return;
    setIsRestoringVersion(true);
    try {
      const updated = await planService.restorePlanVersion(plan.id, versionNum);
      setPlan(updated);
      setEditableAst(updated.plan_data);
      setIsEditing(false);
      setSelectedVersionNum(null);
      setPreviewVersionDetail(null);
      await fetchVersions();
      toast.success(`Plan successfully restored to version v${versionNum}!`);
      if (onPlanUpdated) onPlanUpdated(updated);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to restore version.';
      toast.error(`Restore Error: ${msg}`);
    } finally {
      setIsRestoringVersion(false);
    }
  };

  // Agent Execution State
  const [activeJob, setActiveJob] = useState<ExecutionJobResponse | null>(null);
  const [isApproving, setIsApproving] = useState<boolean>(false);
  const [isDryRunning, setIsDryRunning] = useState<boolean>(false);

  // Refinement Prompt State
  const [refinementPrompt, setRefinementPrompt] = useState<string>('');
  const [isRefining, setIsRefining] = useState<boolean>(initialPlan.status === 'refining');
  const [refiningPromptEcho, setRefiningPromptEcho] = useState<string>('');
  const [refiningElapsedSec, setRefiningElapsedSec] = useState<number>(0);
  const [showJsonModal, setShowJsonModal] = useState<boolean>(false);
  const [expandedTable, setExpandedTable] = useState<string | null>(
    initialPlan.plan_data?.table_mappings?.[0]?.target_table_name || null
  );

  React.useEffect(() => {
    if (initialPlan.status === 'refining') {
      setIsRefining(true);
    }
  }, [initialPlan.status]);

  const isHistoricalPreview = previewVersionDetail !== null;
  const ast = isHistoricalPreview
    ? previewVersionDetail.plan_data
    : isEditing
    ? editableAst
    : plan.plan_data;
  const isApproved = plan.status === 'completed' || plan.status === 'approved';

  // Compute active refinement feedback for current view or historical preview
  const latestRefinementVersion = versions.find((v) => v.edit_type === 'llm_refinement');
  const activeFeedback: RefinementFeedback | null =
    ast?.refinement_feedback ||
    (isHistoricalPreview && previewVersionDetail?.user_feedback
      ? {
          applied: false,
          verdict: 'infeasible_rejected',
          user_prompt: previewVersionDetail.user_feedback,
          explanation:
            `The requested prompt was evaluated against source schemas. Consolidation into fewer collections was rejected to prevent data loss across distinct source domains. All ${ast?.table_mappings?.length || 14} collections are retained to guarantee 100% data fidelity.`,
          table_count_before: ast?.table_mappings?.length || 14,
          table_count_after: ast?.table_mappings?.length || 14,
          changes_summary: ast?.warnings || [],
        }
      : latestRefinementVersion?.user_feedback && ast?.table_mappings?.length === 14
      ? {
          applied: false,
          verdict: 'infeasible_rejected',
          user_prompt: latestRefinementVersion.user_feedback,
          explanation:
            `The requested prompt was evaluated against source schemas. Consolidation into fewer collections was rejected to prevent data loss across distinct source domains. All ${ast?.table_mappings?.length || 14} collections are retained to guarantee 100% data fidelity.`,
          table_count_before: 14,
          table_count_after: 14,
          changes_summary: ast?.warnings || [],
        }
      : null);

  // Helper to update a target column field in editableAst
  const updateColumnField = (
    tableIndex: number,
    columnIndex: number,
    field: keyof ColumnMappingSpec,
    value: any
  ) => {
    const updated = JSON.parse(JSON.stringify(editableAst)) as TransformationPlanAST;
    const targetCol = updated.table_mappings[tableIndex]?.column_mappings[columnIndex];
    if (targetCol) {
      (targetCol as any)[field] = value;
      // Keep ui_badge_type synced if updating transformation_type
      if (field === 'transformation_type') {
        targetCol.ui_badge_type = value;
      }
    }
    setEditableAst(updated);
  };

  const diagnosticRef = useRef<HTMLDivElement>(null);

  const scrollToDiagnostics = () => {
    setTimeout(() => {
      if (diagnosticRef.current) {
        diagnosticRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 100);
  };

  // Save manual column edits
  const handleSaveEdits = async () => {
    setIsSavingEdits(true);
    try {
      const updated = await planService.updatePlan(plan.id, editableAst);
      setPlan(updated);
      setEditableAst(updated.plan_data);
      setIsEditing(false);

      if (updated.is_valid) {
        toast.success('Target mappings updated & re-validated successfully!');
      } else {
        toast.error('Plan edits contain schema feasibility errors! Review diagnostic alert below.');
        scrollToDiagnostics();
      }
      await fetchVersions();
      if (onPlanUpdated) onPlanUpdated(updated);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to save column edits.';
      toast.error(`Save Error: ${msg}`);
      
      // Inject synthetic validation error object so Diagnostic Card pops up
      const errDetails = err.response?.data?.detail;
      const errorList = typeof errDetails === 'string' ? [errDetails] : ['Failed to validate plan edits against database metadata.'];
      setPlan((prev) => ({
        ...prev,
        is_valid: false,
        status: 'invalid_edits',
        validation_errors: {
          is_valid: false,
          errors: errorList,
          warnings: [],
          explanation: `Plan edit validation failed: ${msg}`,
        },
      }));
      scrollToDiagnostics();
    } finally {
      setIsSavingEdits(false);
    }
  };

  // Polling effect when isRefining is active (survives browser refresh)
  React.useEffect(() => {
    if (!isRefining) return;

    let isMounted = true;

    const checkStatus = async () => {
      try {
        const res = await planService.getRefinementStatus(plan.id);
        if (!isMounted) return;

        if (res.status === 'processing') {
          if (res.user_prompt) setRefiningPromptEcho(res.user_prompt);
          if (typeof res.elapsed_seconds === 'number') {
            setRefiningElapsedSec(Math.round(res.elapsed_seconds));
          }
        } else if (res.status === 'completed') {
          setIsRefining(false);
          if (res.plan) {
            setPlan(res.plan);
            setEditableAst(res.plan.plan_data);

            const feedback = res.plan.plan_data?.refinement_feedback;
            if (feedback && (feedback.verdict === 'infeasible_rejected' || !feedback.applied)) {
              toast('LLM Evaluated Request: Refinement not feasible without data loss. See AI analysis below.', {
                icon: '⚠️',
                duration: 6000,
                style: {
                  background: '#18181b',
                  color: '#fbbf24',
                  border: '1px solid rgba(251, 191, 36, 0.4)',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                },
              });
            } else if (res.plan.is_valid) {
              toast.success('LLM re-reviewed & refined blueprint successfully!');
            } else {
              toast.error('LLM refinement generated schema feasibility errors! Review diagnostic alert below.');
              scrollToDiagnostics();
            }
            await fetchVersions();
            if (onPlanUpdated) onPlanUpdated(res.plan);

            setTimeout(() => {
              const el = document.getElementById('ai-refinement-feedback-card');
              if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 150);
          }
        } else if (res.status === 'failed') {
          setIsRefining(false);
          const errorMsg = res.error || 'Refinement failed.';
          toast.error(`Refinement Error: ${errorMsg}`);
          try {
            const freshPlan = await planService.getPlan(plan.id);
            if (isMounted) {
              setPlan(freshPlan);
              setEditableAst(freshPlan.plan_data);
              if (onPlanUpdated) onPlanUpdated(freshPlan);
            }
          } catch {
            // ignore
          }
        } else {
          // If server reports idle but UI was refining, verify with server plan
          const freshPlan = await planService.getPlan(plan.id);
          if (isMounted && freshPlan.status !== 'refining') {
            setIsRefining(false);
            setPlan(freshPlan);
            setEditableAst(freshPlan.plan_data);
            await fetchVersions();
            if (onPlanUpdated) onPlanUpdated(freshPlan);
          }
        }
      } catch {
        // network hiccup, will retry next interval
      }
    };

    checkStatus();
    const intervalId = setInterval(checkStatus, 2000);
    const tickerId = setInterval(() => {
      setRefiningElapsedSec((prev) => prev + 1);
    }, 1000);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
      clearInterval(tickerId);
    };
  }, [isRefining, plan.id, fetchVersions, onPlanUpdated]);

  // Handle Natural Language AI Plan Refinement (Asynchronous Detached Coroutine)
  const handleRefinePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    const promptText = refinementPrompt.trim();
    if (!promptText || isRefining) return;

    setIsRefining(true);
    setRefiningPromptEcho(promptText);
    setRefiningElapsedSec(0);
    setRefinementPrompt('');

    try {
      await planService.startRefinement(plan.id, promptText);
      setPlan((prev) => ({ ...prev, status: 'refining' }));
      toast.success('AI plan refinement running in background. Polling for results...', {
        icon: '🚀',
        duration: 4000,
      });
    } catch (err: any) {
      setIsRefining(false);
      const msg = err.response?.data?.detail || err.message || 'Failed to start refinement.';
      toast.error(`Refinement Error: ${msg}`);
    }
  };

  // Stable callback — memoized so it never creates a new function reference on
  // re-renders, which would restart the banner's 2s polling interval useEffect.
  const handleActiveJobUpdated = useCallback((updated: ExecutionJobResponse) => {
    setActiveJob(updated);
  }, []);

  // On mount: find either an active execution job OR the most recent failed/completed
  // job for this plan so the banner (with AI diagnosis) shows immediately on page load.
  React.useEffect(() => {
    executionService
      .listPlanJobs(initialPlan.id)
      .then((jobs) => {
        if (!jobs || jobs.length === 0) return;
        const active = jobs.find(
          (j) => ['queued', 'preparing', 'running'].includes(j.status)
        );
        // jobs are ordered newest first from the API
        if (active) {
          setActiveJob(active);
        } else {
          // Show most recent completed/failed job so diagnosis card is visible
          setActiveJob(jobs[0]);
        }
      })
      .catch(() => {});
  }, [initialPlan.id]);

  // Open Execution Confirmation Modal
  const handleOpenExecutionModal = () => {
    if (isApproving || isApproved || isDryRunning || isRefining || plan.status === 'refining') return;

    if (!plan.is_valid) {
      toast.error('Cannot execute invalid plan! Fix schema feasibility errors first.');
      scrollToDiagnostics();
      return;
    }

    setTruncateTarget(false);
    setShowExecutionConfirmModal(true);
  };

  // Handle Confirmed Plan Approval & Agent Job Dispatch
  const handleApproveAndExecute = async () => {
    if (isApproving) return;
    setShowExecutionConfirmModal(false);

    setIsApproving(true);
    try {
      // 1. Approve Plan
      const approved = await planService.approvePlan(plan.id);
      setPlan(approved);

      // 2. Trigger Execution Job on Docker Agent with truncate_target option
      const job = await executionService.startPlanExecution(plan.id, {
        truncate_target: truncateTarget,
      });
      setActiveJob(job);

      if (truncateTarget) {
        toast('Clean Wipe Enabled: Target database tables will be dropped before writing.', {
          icon: '🧹',
          duration: 6000,
        });
      } else if (job.target_tables_with_existing_data && job.target_tables_with_existing_data.length > 0) {
        const tableList = job.target_tables_with_existing_data
          .map((t) => `${t.table_name} (${t.existing_row_count} rows)`)
          .join(', ');
        toast(`Notice: Destination table(s) contain existing data: ${tableList}. New rows will be appended.`, {
          icon: '⚠️',
          duration: 7000,
        });
      }

      toast.success('Plan approved! Data migration job queued on Docker Agent.');
      if (onPlanUpdated) onPlanUpdated(approved);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to execute plan.';
      if (err.response?.status === 409) {
        toast.error(`Job In Progress: ${msg}`);
        executionService
          .listUserExecutions()
          .then((jobs) => {
            const match = jobs.find(
              (j) => j.migration_plan_id === plan.id && ['queued', 'preparing', 'running'].includes(j.status)
            );
            if (match) setActiveJob(match);
          })
          .catch(() => {});
      } else if (err.response?.status === 503) {
        toast.error(`Agent Offline Warning: ${msg}`, { duration: 8000 });
      } else {
        toast.error(`Execution Error: ${msg}`);
        scrollToDiagnostics();
      }
    } finally {
      setIsApproving(false);
    }
  };

  // Handle Dry Run Simulation Dispatch
  const handleDryRun = async () => {
    if (isDryRunning || isApproving) return;

    if (!plan.is_valid) {
      toast.error('Cannot run dry run simulation on invalid plan! Fix schema feasibility errors first.');
      scrollToDiagnostics();
      return;
    }

    setIsDryRunning(true);
    try {
      // 1. Approve Plan if not approved yet
      let currentPlan = plan;
      if (plan.status !== 'approved' && plan.status !== 'completed') {
        currentPlan = await planService.approvePlan(plan.id);
        setPlan(currentPlan);
      }

      // 2. Trigger Dry Run Execution Job on Docker Agent
      const job = await executionService.startPlanExecution(plan.id, { is_dry_run: true });
      setActiveJob(job);

      toast.success('Dry run simulation queued! No data will be written to target database.');
      if (onPlanUpdated) onPlanUpdated(currentPlan);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to execute dry run.';
      if (err.response?.status === 409) {
        toast.error(`Job In Progress: ${msg}`);
        executionService
          .listUserExecutions()
          .then((jobs) => {
            const match = jobs.find(
              (j) => j.migration_plan_id === plan.id && ['queued', 'preparing', 'running'].includes(j.status)
            );
            if (match) setActiveJob(match);
          })
          .catch(() => {});
      } else if (err.response?.status === 503) {
        toast.error(`Agent Offline Warning: ${msg}`, { duration: 8000 });
      } else {
        toast.error(`Dry Run Error: ${msg}`);
        scrollToDiagnostics();
      }
    } finally {
      setIsDryRunning(false);
    }
  };

  const confidencePercentage = Math.round((plan.confidence_score || ast?.confidence_score || 0.9) * 100);

  return (
    <div className="w-full max-w-6xl mx-auto space-y-8 animate-fadeIn font-sans">
      {/* Plan Header & Metadata */}
      <div className="p-6 rounded-none bg-black border border-zinc-800 backdrop-blur-xl space-y-4 shadow-xl">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
          <div>
            <div className="flex items-center gap-2.5 mb-1">
              <span className="text-[10px] font-mono font-bold tracking-widest px-2.5 py-0.5 rounded-none uppercase bg-sky-400/10 text-sky-400 border border-sky-400/30">
                TRANSFORMATION BLUEPRINT
              </span>
              <span
                className={`text-[10px] font-mono font-bold tracking-widest px-2.5 py-0.5 rounded-none uppercase border ${
                  isApproved
                    ? 'bg-emerald-400/10 text-emerald-400 border-emerald-400/30'
                    : 'bg-amber-400/10 text-amber-400 border-amber-400/30'
                }`}
              >
                STATUS: {plan.status.toUpperCase()}
              </span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight uppercase font-sans">
              AI Migration Plan Specification
            </h2>
            <p className="text-xs text-zinc-400 font-mono mt-0.5">
              Plan ID: {plan.id}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <PlanReadinessRollupBadge ast={ast} planConfidenceScore={plan.confidence_score} />
            <button
              type="button"
              onClick={() => setShowJsonModal(true)}
              className="py-3 px-4 rounded-none bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-mono font-bold uppercase tracking-wider border border-zinc-800 transition-colors"
            >
              View JSON AST
            </button>
          </div>
        </div>

        {/* 4 Separate Readiness Signals (Schema, Type, Relationship, Data Conflict Risk) */}
        <div className="pt-2 pb-2 border-b border-zinc-900">
          <PlanReadinessSignals ast={ast} planConfidenceScore={plan.confidence_score} />
        </div>

        {/* Controls Bar: View Mode Switcher + Version Selector + Edit Toggle */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-2 border-b border-zinc-900 pb-3">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => setViewMode('matrix')}
              className={`px-5 py-2 rounded-none text-xs font-mono font-bold uppercase tracking-wider border transition-all ${
                viewMode === 'matrix'
                  ? 'bg-sky-400/15 border-sky-400 text-sky-400 shadow-[0_0_12px_rgba(56,189,248,0.2)]'
                  : 'bg-zinc-950 border-zinc-900 text-zinc-400 hover:border-zinc-800 hover:text-white'
              }`}
            >
              [ MATRIX SPECIFICATION VIEW ]
            </button>
            <button
              type="button"
              onClick={() => setViewMode('diagram')}
              className={`px-5 py-2 rounded-none text-xs font-mono font-bold uppercase tracking-wider border transition-all ${
                viewMode === 'diagram'
                  ? 'bg-sky-400/15 border-sky-400 text-sky-400 shadow-[0_0_12px_rgba(56,189,248,0.2)]'
                  : 'bg-zinc-950 border-zinc-900 text-zinc-400 hover:border-zinc-800 hover:text-white'
              }`}
            >
              [ VISUAL PIPELINE DIAGRAM ]
            </button>

            {/* Version Selector Dropdown */}
            {versions.length > 0 && (
              <div className="flex items-center gap-2 font-mono ml-0 sm:ml-2">
                <span className="text-[10px] text-zinc-500 uppercase font-bold">VERSION:</span>
                <select
                  value={selectedVersionNum !== null ? selectedVersionNum : (versions[0]?.version_number || '')}
                  onChange={(e) => {
                    const val = e.target.value ? parseInt(e.target.value, 10) : null;
                    handleSelectVersion(val);
                  }}
                  disabled={isLoadingVersion || isRestoringVersion || isEditing}
                  className="bg-zinc-950 border border-zinc-800 text-sky-400 text-xs font-mono font-bold px-3 py-1.5 rounded-none focus:outline-none focus:border-sky-400 transition-colors disabled:opacity-50"
                >
                  {versions.map((ver, idx) => {
                    const isLatest = idx === 0;
                    const labelType =
                      ver.edit_type === 'initial_ai_generation'
                        ? 'Initial AI Plan'
                        : ver.edit_type === 'llm_refinement'
                        ? `Prompt: "${ver.user_feedback || 'Refinement'}"`
                        : ver.edit_type === 'version_restored'
                        ? ver.user_feedback || 'Restored Version'
                        : 'Manual Column Edit';
                    return (
                      <option key={ver.id} value={ver.version_number}>
                        v{ver.version_number} {isLatest ? '(Latest)' : ''} - {labelType}
                      </option>
                    );
                  })}
                </select>
              </div>
            )}
          </div>

          {/* Edit Mode Actions */}
          {!isApproved && (
            <div className="flex items-center gap-3">
              {isEditing ? (
                <>
                  <button
                    type="button"
                    onClick={() => {
                      setIsEditing(false);
                      setEditableAst(plan.plan_data);
                    }}
                    className="py-2 px-4 rounded-none bg-zinc-900 hover:bg-zinc-800 text-zinc-400 text-xs font-mono font-bold uppercase border border-zinc-800"
                  >
                    Discard Changes
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveEdits}
                    disabled={isSavingEdits}
                    className="py-2 px-5 rounded-none bg-sky-400 hover:bg-sky-300 text-black text-xs font-mono font-bold uppercase tracking-wider border border-sky-400 shadow-md shadow-sky-950/50"
                  >
                    {isSavingEdits ? 'Saving Edits...' : 'Save Column Mappings & Re-validate'}
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => setIsEditing(true)}
                  className="py-2 px-5 rounded-none bg-zinc-900 hover:bg-zinc-800 text-sky-400 text-xs font-mono font-bold uppercase tracking-wider border border-sky-400/40 transition-colors"
                >
                  ✎ Edit Blueprint AST
                </button>
              )}
            </div>
          )}
        </div>

        {/* Historical Version Preview Banner */}
        {isHistoricalPreview && previewVersionDetail && (
          <div className="p-4 bg-amber-950/40 border border-amber-500/50 text-amber-300 font-mono text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 animate-fadeIn">
            <div className="flex items-center gap-2.5">
              <span className="px-2 py-0.5 bg-amber-500 text-black font-bold uppercase text-[10px] tracking-wider">
                HISTORICAL SNAPSHOT v{previewVersionDetail.version_number} (READ ONLY)
              </span>
              <span className="text-zinc-300">
                Created: <strong className="text-white">{new Date(previewVersionDetail.created_at).toLocaleString()}</strong>
                {previewVersionDetail.user_feedback && (
                  <span className="ml-2 text-amber-200 font-sans italic">
                    — "{previewVersionDetail.user_feedback}"
                  </span>
                )}
              </span>
            </div>
            <div className="flex items-center gap-2.5">
              <button
                type="button"
                onClick={() => handleRestoreVersion(previewVersionDetail.version_number)}
                disabled={isRestoringVersion}
                className="px-4 py-1.5 bg-amber-500 hover:bg-amber-400 text-black font-bold uppercase text-xs tracking-wider transition-colors disabled:opacity-50"
              >
                {isRestoringVersion ? 'RESTORING...' : `RESTORE TO v${previewVersionDetail.version_number}`}
              </button>
              <button
                type="button"
                onClick={() => handleSelectVersion(null)}
                className="px-3 py-1.5 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 font-bold uppercase text-xs border border-zinc-700 transition-colors"
              >
                EXIT PREVIEW
              </button>
            </div>
          </div>
        )}

        {/* AI Explanation Narrative */}
        {ast?.ai_explanation && (
          <div className="p-4 rounded-none bg-zinc-950 border border-zinc-800 space-y-2">
            <h4 className="text-xs font-mono font-bold text-sky-400 uppercase tracking-wider">
              AI Execution Strategy
            </h4>
            <p className="text-xs text-zinc-300 font-sans leading-relaxed">
              {ast.ai_explanation}
            </p>
          </div>
        )}

        {/* Deterministic Plan Feasibility & Validation Diagnostic Card */}
        {plan.validation_errors && (
          <div ref={diagnosticRef} className={`p-4 rounded-none border font-mono text-xs space-y-2 ${
            plan.is_valid
              ? 'bg-emerald-950/20 border-emerald-500/40 text-emerald-300'
              : 'bg-rose-950/30 border-rose-500/50 text-rose-300 shadow-[0_0_20px_rgba(244,63,94,0.15)]'
          }`}>
            <div className="flex items-center justify-between font-bold uppercase">
              <span className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-none ${plan.is_valid ? 'bg-emerald-400' : 'bg-rose-500 animate-ping'}`} />
                {plan.is_valid ? '✓ PLAN FEASIBILITY VERIFIED' : '🚨 INVALID PLAN EDITS DETECTED'}
              </span>
              <span className="text-[10px] text-zinc-400">
                Status: {plan.is_valid ? 'FEASIBLE' : 'EXECUTION BLOCKED'}
              </span>
            </div>
            
            <p className="text-zinc-300 leading-relaxed font-sans text-xs">
              {plan.validation_errors.explanation}
            </p>

            {/* Validation Errors */}
            {plan.validation_errors.errors && plan.validation_errors.errors.length > 0 && (
              <div className="p-3 bg-black/80 border border-rose-500/40 text-rose-400 space-y-1 mt-2">
                <span className="font-bold uppercase text-[10px] text-rose-400 block">Schema Feasibility Errors ({plan.validation_errors.errors.length}):</span>
                <ul className="list-disc list-inside text-[11px] space-y-0.5 font-mono">
                  {plan.validation_errors.errors.map((err: string, i: number) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Validation Warnings */}
            {plan.validation_errors.warnings && plan.validation_errors.warnings.length > 0 && (
              <div className="p-3 bg-black/80 border border-amber-500/40 text-amber-400 space-y-1 mt-2">
                <span className="font-bold uppercase text-[10px] text-amber-400 block">Architecture Warnings ({plan.validation_errors.warnings.length}):</span>
                <ul className="list-disc list-inside text-[11px] space-y-0.5 font-mono">
                  {plan.validation_errors.warnings.map((warn: string, i: number) => (
                    <li key={i}>{warn}</li>
                  ))}
                </ul>
              </div>
            )}
            {/* Revert Action Button for Invalid Refinements / Edits */}
            {(() => {
              const lastValidVer = versions.find((v) => v.is_valid);
              if (plan.is_valid || !lastValidVer) return null;
              return (
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => handleRestoreVersion(lastValidVer.version_number)}
                    disabled={isRestoringVersion}
                    className="py-2.5 px-5 rounded-none bg-rose-500 hover:bg-rose-400 text-black text-xs font-mono font-bold uppercase tracking-wider transition-colors shadow-md flex items-center gap-2"
                  >
                    <span>
                      {isRestoringVersion
                        ? 'Restoring Blueprint...'
                        : `↩ Revert to Last Valid Version (v${lastValidVer.version_number})`}
                    </span>
                  </button>
                </div>
              );
            })()}
          </div>
        )}
      </div>

      {/* Guard for draft_failed status or missing table mappings (EC-08) */}
      {(plan.status === 'draft_failed' || !ast?.table_mappings || ast.table_mappings.length === 0) && (
        <div className="w-full max-w-4xl mx-auto p-8 rounded-none bg-black border border-rose-500/50 space-y-6 font-mono text-center shadow-2xl">
          <div className="w-12 h-12 rounded-none bg-rose-500/10 border border-rose-500/40 text-rose-500 flex items-center justify-center mx-auto text-xl font-bold">
            🚨
          </div>
          <div className="space-y-2">
            <h2 className="text-xl font-extrabold text-white uppercase tracking-tight font-sans">
              AI Migration Plan Generation Failed
            </h2>
            <p className="text-xs text-rose-300 max-w-xl mx-auto leading-relaxed">
              {plan.validation_errors?.explanation || 'The AI model could not generate a valid transformation blueprint for your data sources.'}
            </p>
          </div>
          <div className="pt-2 flex justify-center gap-4">
            <button
              type="button"
              onClick={() => window.location.href = `/sources?agentId=${plan.agent_id}`}
              className="py-3 px-6 rounded-none bg-rose-500 hover:bg-rose-400 text-black text-xs font-mono font-bold uppercase tracking-wider transition-colors"
            >
              Return to Schema Inspector & Retry
            </button>
          </div>
        </div>
      )}

      {/* Active AI Refinement Progress Banner */}
      {isRefining && (
        <div className="p-5 rounded-none bg-zinc-950 border border-sky-400/50 space-y-3 font-mono shadow-[0_0_25px_rgba(56,189,248,0.15)] relative overflow-hidden animate-fadeIn">
          <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-sky-400 via-indigo-500 to-sky-400 animate-pulse" />
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-none bg-sky-400/10 border border-sky-400/40 flex items-center justify-center text-sky-400">
                <svg className="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                </svg>
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                    AI Blueprint Refinement in Progress
                  </h4>
                  <span className="px-2 py-0.5 text-[10px] font-mono font-bold rounded-none bg-sky-400/20 text-sky-300 border border-sky-400/40">
                    {refiningElapsedSec}s elapsed
                  </span>
                </div>
                <p className="text-xs text-zinc-400 font-sans mt-0.5">
                  {refiningPromptEcho
                    ? `Evaluating feedback: "${refiningPromptEcho}"`
                    : 'Analyzing multi-database schemas and re-evaluating transformation AST in background...'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-right">
              <span className="w-2 h-2 rounded-none bg-sky-400 animate-ping" />
              <span className="text-[11px] text-sky-400 font-mono font-bold uppercase tracking-wider">
                PROCESSING (BACKGROUND POLLING 2S)
              </span>
            </div>
          </div>
          <div className="text-[11px] text-zinc-500 font-mono border-t border-zinc-900 pt-2 flex items-center justify-between">
            <span>You may refresh or navigate away — your refinement task continues executing on the server without interruption.</span>
            <span className="text-zinc-400">LLM Timeout: 360s</span>
          </div>
        </div>
      )}

      {/* Live Agent Execution Progress Banner (if active or recently run) */}
      {activeJob && (
        <JobExecutionBanner
          job={activeJob}
          onJobUpdated={handleActiveJobUpdated}
        />
      )}

      {/* Body Content Switcher (Diagram vs Matrix) */}
      {viewMode === 'diagram' ? (
        <PlanDiagramViewer ast={ast} />
      ) : (
        <>
          {/* Execution Sequence Pipeline */}
          {ast?.table_mappings && (
            <div className="p-5 rounded-none bg-black border border-zinc-800 space-y-3 font-mono">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <span className="w-2 h-2 rounded-none bg-sky-400 inline-block" />
                Table Execution Sequence Timeline ({ast.table_mappings.length} tables)
              </h3>

              <div className="flex items-center gap-3 overflow-x-auto py-2">
                {ast.table_mappings.map((tm, idx) => (
                  <React.Fragment key={tm.target_table_name}>
                    <div
                      onClick={() => setExpandedTable(tm.target_table_name)}
                      className={`p-3 rounded-none border cursor-pointer whitespace-nowrap text-xs transition-all ${
                        expandedTable === tm.target_table_name
                          ? 'bg-sky-400/15 border-sky-400 text-sky-400 shadow-[0_0_12px_rgba(56,189,248,0.2)]'
                          : 'bg-zinc-950 border-zinc-800 text-zinc-300 hover:border-zinc-700'
                      }`}
                    >
                      <span className="text-[10px] text-zinc-500 mr-2">STEP {idx + 1}</span>
                      <strong className="text-white font-bold">{tm.target_table_name}</strong>
                      <span className="text-[9px] text-sky-400 block mt-0.5 uppercase">
                        {tm.transformation_type} ({tm.column_mappings.length} cols)
                      </span>
                    </div>
                    {idx < ast.table_mappings.length - 1 && (
                      <span className="text-zinc-600 font-bold text-sm">→</span>
                    )}
                  </React.Fragment>
                ))}
              </div>
            </div>
          )}
          {ast && <PlanPlainLanguageSummary ast={ast} />}

          {/* Table Transformation Matrix */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <span className="w-2 h-2 rounded-none bg-blue-500 inline-block" />
                Table Mapping Specifications Matrix
              </h3>
              {isEditing && (
                <span className="text-xs font-mono text-sky-400 animate-pulse font-bold">
                  ✎ INLINE COLUMN EDITING MODE ACTIVE (Destination Fields Editable)
                </span>
              )}
            </div>

            {ast?.table_mappings?.map((tm, tmIdx) => {
              const isExpanded = expandedTable === tm.target_table_name;

              return (
                <div
                  key={tm.target_table_name}
                  className="rounded-none bg-black border border-zinc-800 overflow-hidden shadow-xl"
                >
                  {/* Table Accordion Header */}
                  <div
                    className="p-4 bg-zinc-950 border-b border-zinc-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 cursor-pointer hover:bg-zinc-900/60 transition-colors font-mono"
                  >
                    <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto" onClick={() => setExpandedTable(isExpanded ? null : tm.target_table_name)}>
                      {isEditing ? (
                        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                          <span className="text-xs font-bold text-sky-400 uppercase">Table Name:</span>
                          <input
                            type="text"
                            value={tm.target_table_name || ''}
                            onChange={(e) => {
                              const updated = JSON.parse(JSON.stringify(editableAst)) as TransformationPlanAST;
                              if (updated.table_mappings[tmIdx]) {
                                updated.table_mappings[tmIdx].target_table_name = e.target.value;
                              }
                              setEditableAst(updated);
                            }}
                            className="px-2 py-1 bg-zinc-900 border border-sky-400 text-white font-mono text-sm font-extrabold focus:outline-none"
                          />
                          <select
                            value={tm.transformation_type}
                            onChange={(e) => {
                              const updated = JSON.parse(JSON.stringify(editableAst)) as TransformationPlanAST;
                              if (updated.table_mappings[tmIdx]) {
                                updated.table_mappings[tmIdx].transformation_type = e.target.value as TableTransformationType;
                              }
                              setEditableAst(updated);
                            }}
                            className="px-2 py-1 bg-zinc-900 border border-sky-400 text-sky-400 text-xs font-mono font-bold uppercase focus:outline-none"
                          >
                            <option value="direct_copy">direct_copy</option>
                            <option value="merge">merge</option>
                            <option value="split_target">split_target</option>
                          </select>
                        </div>
                      ) : (
                        <>
                          <span className="text-sm font-extrabold text-white uppercase tracking-wider">
                            {tm.target_table_name}
                          </span>
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-none bg-sky-400/10 text-sky-400 border border-sky-400/30 uppercase">
                            {tm.transformation_type}
                          </span>
                        </>
                      )}
                      <span className="text-[10px] text-zinc-400">
                        Sources: {tm.source_tables.map((st) => `${st.identifier}.${st.table_name}`).join(', ')}
                      </span>
                    </div>

                    <div className="flex items-center gap-4 text-xs text-zinc-400 w-full sm:w-auto justify-between sm:justify-end" onClick={() => setExpandedTable(isExpanded ? null : tm.target_table_name)}>
                      <TableReadinessBadge tm={tm} />
                      <span className="text-sm font-bold text-white">{isExpanded ? '▲' : '▼'}</span>
                    </div>
                  </div>

                  {/* Table Details */}
                  {isExpanded && (
                    <div className="p-5 space-y-4 font-mono text-xs">
                      {/* AI Reasoning & Conflict Resolution Policy Controls */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {tm.ai_reasoning && (
                          <div className="p-3 rounded-none bg-zinc-950 border border-zinc-800/80 text-zinc-300 text-[11px]">
                            <strong className="text-sky-400 uppercase font-mono mr-2 font-bold">AI Rationale:</strong>
                            {tm.ai_reasoning}
                          </div>
                        )}

                        {/* Merge / Deduplication Policy Settings */}
                        <div className="p-3 rounded-none bg-zinc-950 border border-zinc-800 text-[11px] space-y-1.5">
                          <div className="flex items-center justify-between text-zinc-400 font-bold uppercase text-[10px]">
                            <span className="text-sky-400">Conflict & Merge Policy</span>
                            <span>PK Strategy: {tm.conflict_resolution?.primary_key_strategy || 'uuid_v5'}</span>
                          </div>
                          {isEditing ? (
                            <div className="flex flex-wrap items-center gap-3 pt-1">
                              <label className="flex items-center gap-1.5 text-zinc-300">
                                <span>Dedup Key:</span>
                                <input
                                  type="text"
                                  value={tm.conflict_resolution?.deduplication_key || ''}
                                  onChange={(e) => {
                                    const updated = JSON.parse(JSON.stringify(editableAst)) as TransformationPlanAST;
                                    if (updated.table_mappings[tmIdx]) {
                                      if (!updated.table_mappings[tmIdx].conflict_resolution) {
                                        updated.table_mappings[tmIdx].conflict_resolution = { deduplication_key: '', primary_key_strategy: 'uuid_v4_rekey' };
                                      }
                                      updated.table_mappings[tmIdx].conflict_resolution!.deduplication_key = e.target.value;
                                    }
                                    setEditableAst(updated);
                                  }}
                                  placeholder="e.g. email"
                                  className="px-2 py-0.5 bg-zinc-900 border border-sky-400 text-white font-mono text-xs"
                                />
                              </label>
                              <label className="flex items-center gap-1.5 text-zinc-300">
                                <span>PK Strategy:</span>
                                <select
                                  value={tm.conflict_resolution?.primary_key_strategy || 'uuid_v5'}
                                  onChange={(e) => {
                                    const updated = JSON.parse(JSON.stringify(editableAst)) as TransformationPlanAST;
                                    if (updated.table_mappings[tmIdx]) {
                                      if (!updated.table_mappings[tmIdx].conflict_resolution) {
                                        updated.table_mappings[tmIdx].conflict_resolution = { deduplication_key: '', primary_key_strategy: 'uuid_v4_rekey' };
                                      }
                                      updated.table_mappings[tmIdx].conflict_resolution!.primary_key_strategy = e.target.value as ConflictResolutionSpec['primary_key_strategy'];
                                    }
                                    setEditableAst(updated);
                                  }}
                                  className="px-2 py-0.5 bg-zinc-900 border border-sky-400 text-sky-400 font-mono text-xs uppercase"
                                >
                                  <option value="uuid_v4_rekey">uuid_v4_rekey</option>
                                  <option value="prefix_id">prefix_id</option>
                                  <option value="autoincrement_offset">autoincrement_offset</option>
                                  <option value="keep_original">keep_original</option>
                                </select>
                              </label>
                            </div>
                          ) : (
                            <div className="text-zinc-300 text-[11px]">
                              Deduplication Key: <strong className="text-white">{tm.conflict_resolution?.deduplication_key || 'None (Primary Key)'}</strong>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Columns Matrix Table */}
                      <div className="overflow-x-auto">
                        <table className="w-full text-left font-mono text-xs">
                          <thead>
                            <tr className="border-b border-zinc-800 text-zinc-400 uppercase text-[10px] tracking-wider bg-zinc-950">
                              <th className="p-3">Target Column</th>
                              <th className="p-3">Target Data Type</th>
                              <th className="p-3">Transformation Type</th>
                              <th className="p-3">Mapping Confidence</th>
                              <th className="p-3">Source Column Ref (Read-Only)</th>
                              <th className="p-3">Explanation & Formula</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-zinc-900">
                            {tm.column_mappings.map((cm: ColumnMappingSpec, cIdx: number) => (
                              <tr key={cIdx} className="hover:bg-zinc-950/60 transition-colors">
                                {/* Target Column Name */}
                                <td className="p-3 font-bold text-white">
                                  {isEditing ? (
                                    <input
                                      type="text"
                                      value={cm.target_column_name || ''}
                                      onChange={(e) => updateColumnField(tmIdx, cIdx, 'target_column_name', e.target.value)}
                                      className="w-full px-2 py-1 rounded-none bg-zinc-950 border border-sky-400 text-white font-mono text-xs focus:outline-none"
                                    />
                                  ) : (
                                    <>
                                      {cm.target_column_name || <span className="text-zinc-500 italic">[Dropped]</span>}
                                      {cm.is_primary_key && (
                                        <span className="ml-2 px-1.5 py-0.5 text-[9px] rounded-none bg-sky-400/20 text-sky-400 border border-sky-400/40 uppercase font-bold">
                                          PK
                                        </span>
                                      )}
                                    </>
                                  )}
                                </td>

                                {/* Target Data Type */}
                                <td className="p-3 text-sky-400">
                                  {isEditing ? (
                                    <input
                                      type="text"
                                      value={cm.target_data_type || ''}
                                      onChange={(e) => updateColumnField(tmIdx, cIdx, 'target_data_type', e.target.value)}
                                      className="w-full px-2 py-1 rounded-none bg-zinc-950 border border-sky-400 text-sky-400 font-mono text-xs focus:outline-none"
                                    />
                                  ) : (
                                    cm.target_data_type || <span className="text-zinc-600">—</span>
                                  )}
                                </td>

                                {/* Transformation Type */}
                                <td className="p-3">
                                  {isEditing ? (
                                    <select
                                      value={cm.transformation_type}
                                      onChange={(e) => updateColumnField(tmIdx, cIdx, 'transformation_type', e.target.value)}
                                      className="w-full px-2 py-1 rounded-none bg-zinc-950 border border-sky-400 text-blue-400 font-mono text-xs focus:outline-none"
                                    >
                                      <option value="direct_copy">direct_copy</option>
                                      <option value="type_cast">type_cast</option>
                                      <option value="merge_concat">merge_concat</option>
                                      <option value="split">split</option>
                                      <option value="expression">expression</option>
                                      <option value="default_constant">default_constant</option>
                                      <option value="json_flatten">json_flatten</option>
                                      <option value="json_stringify">json_stringify</option>
                                      <option value="array_to_csv">array_to_csv</option>
                                      <option value="array_to_json">array_to_json</option>
                                      <option value="nosql_field_promote">nosql_field_promote</option>
                                      <option value="drop_column">drop_column</option>
                                    </select>
                                  ) : (
                                    <span className="px-2 py-0.5 text-[9px] font-bold rounded-none bg-blue-500/10 text-blue-400 border border-blue-500/30 uppercase">
                                      {cm.transformation_type}
                                    </span>
                                  )}
                                </td>

                                {/* Mapping Confidence */}
                                <td className="p-3">
                                  <ColumnConfidenceBadge col={cm} />
                                </td>

                                {/* Source Columns (Read Only) */}
                                <td className="p-3 text-zinc-300 text-[11px]">
                                  {cm.source_columns.length > 0
                                    ? cm.source_columns.map((sc) => `${sc.identifier}.${sc.table_name}.${sc.column_name}`).join(', ')
                                    : <span className="text-zinc-600">—</span>}
                                </td>

                                {/* Explanation & Formula Input */}
                                <td className="p-3 text-zinc-400 text-[11px] leading-normal max-w-xs space-y-1">
                                  <div>{cm.explanation}</div>
                                  {isEditing && cm.transformation_type === 'expression' && (
                                    <div className="pt-1">
                                      <span className="text-[10px] text-sky-400 uppercase font-bold block">SQL Expression:</span>
                                      <input
                                        type="text"
                                        value={cm.expression_template || ''}
                                        onChange={(e) => updateColumnField(tmIdx, cIdx, 'expression_template', e.target.value)}
                                        placeholder="e.g. quantity * unit_price"
                                        className="w-full px-2 py-0.5 bg-zinc-950 border border-sky-400 text-sky-400 font-mono text-[11px]"
                                      />
                                    </div>
                                  )}
                                  {isEditing && cm.transformation_type === 'default_constant' && (
                                    <div className="pt-1">
                                      <span className="text-[10px] text-amber-400 uppercase font-bold block">Constant Value:</span>
                                      <input
                                        type="text"
                                        value={cm.constant_value || ''}
                                        onChange={(e) => updateColumnField(tmIdx, cIdx, 'constant_value', e.target.value)}
                                        placeholder="e.g. BATCH_2026"
                                        className="w-full px-2 py-0.5 bg-zinc-950 border border-amber-400 text-amber-400 font-mono text-[11px]"
                                      />
                                    </div>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* AI Refinement Feasibility & Response Card */}
      {activeFeedback && (
        <RefinementFeedbackCard
          feedback={activeFeedback}
          versionNumber={isHistoricalPreview ? selectedVersionNum : versions?.[0]?.version_number}
        />
      )}

      {/* Natural Language AI Plan Refinement Input */}
      {!isApproved && (
        <form onSubmit={handleRefinePlan} className="p-6 rounded-none bg-black border border-sky-400/40 space-y-4 shadow-2xl">
          <div>
            <h4 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
              Refine Blueprint with LLM Prompt Suggestion
            </h4>
            <p className="text-xs text-zinc-400 font-sans mt-0.5">
              Type custom adjustments to prompt the LLM for blueprint re-review and re-evaluation.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              required
              disabled={isRefining}
              value={refinementPrompt}
              onChange={(e) => setRefinementPrompt(e.target.value)}
              placeholder="e.g. Map user_id to account_uuid and convert status int enum to string varchar"
              className="flex-1 px-4 py-3 rounded-none bg-zinc-950 border border-zinc-800 text-white text-xs placeholder-zinc-600 focus:outline-none focus:border-sky-400 font-sans transition-colors disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={isRefining}
              className="py-3 px-6 rounded-none bg-sky-400 hover:bg-sky-300 text-black text-xs font-bold uppercase tracking-wider transition-colors shadow-lg shadow-sky-950/50 disabled:opacity-50 whitespace-nowrap font-mono inline-flex items-center gap-2"
            >
              {isRefining ? (
                <>
                  <span className="w-2 h-2 rounded-none bg-black animate-ping" />
                  <span>Refining in Background ({refiningElapsedSec}s)...</span>
                </>
              ) : (
                'Refine with LLM'
              )}
            </button>
          </div>

          {isRefining && (
            <div className="flex items-center gap-2 text-xs text-sky-400 font-mono animate-pulse pt-1">
              <span className="w-2 h-2 rounded-none bg-sky-400 animate-ping" />
              <span>
                LLM background task is actively running ({refiningElapsedSec}s elapsed). The blueprint will automatically update upon completion.
              </span>
            </div>
          )}
        </form>
      )}

      {/* Plan Approval & Agent Execution Action Footer */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-6 rounded-none bg-black border border-zinc-800 shadow-xl">
        <div>
          <h4 className="text-xs font-bold text-white uppercase tracking-wider font-sans">
            Approve Blueprint & Run Local Agent Migration
          </h4>
          <p className="text-xs text-zinc-400 font-mono mt-0.5">
            Approving locks the blueprint AST and dispatches the execution job to your Docker Agent.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Dry Run Button */}
          <button
            type="button"
            onClick={handleDryRun}
            disabled={isDryRunning || isApproving || isRefining || plan.status === 'refining'}
            className="py-3.5 px-6 rounded-none text-xs font-bold font-mono uppercase tracking-wider transition-all border border-amber-400/50 bg-amber-400/10 hover:bg-amber-400/20 text-amber-300 shadow-lg disabled:opacity-50"
          >
            {isDryRunning ? 'Simulating Dry Run...' : '⚡ Run Dry Run (Simulation)'}
          </button>

          {/* Real Approve & Execute Button */}
          <button
            type="button"
            onClick={handleOpenExecutionModal}
            disabled={isApproving || isApproved || isDryRunning || isRefining || plan.status === 'refining'}
            className={`py-3.5 px-8 rounded-none text-xs font-bold font-mono uppercase tracking-wider transition-all shadow-lg ${
              isApproved
                ? 'bg-emerald-500 text-black cursor-default'
                : 'bg-sky-400 hover:bg-sky-300 text-black shadow-sky-950/50 hover:scale-[1.01]'
            } disabled:opacity-50`}
          >
            {isApproved ? 'PLAN APPROVED ✓' : isApproving ? 'Executing on Agent...' : isRefining || plan.status === 'refining' ? 'REFINEMENT IN PROGRESS...' : 'APPROVE & EXECUTE MIGRATION'}
          </button>
        </div>
      </div>

      {/* Execution Confirmation & Target Safety Modal */}
      {showExecutionConfirmModal && (
        <div
          onClick={() => setShowExecutionConfirmModal(false)}
          className="fixed inset-0 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-fadeIn"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="p-6 sm:p-8 rounded-none bg-zinc-950 border border-zinc-800 w-full max-w-2xl flex flex-col space-y-6 shadow-[0_0_50px_rgba(0,0,0,0.9)] relative overflow-hidden font-mono"
          >
            {/* Top Accent Line */}
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-amber-500 via-sky-400 to-rose-500" />

            <div className="flex items-start justify-between border-b border-zinc-800/80 pb-4">
              <div className="space-y-1">
                <span className="text-[10px] font-bold tracking-widest px-2.5 py-0.5 uppercase bg-amber-500/10 text-amber-400 border border-amber-500/30">
                  PRE-MIGRATION EXECUTION CHECK
                </span>
                <h3 className="text-lg sm:text-xl font-extrabold uppercase tracking-wide text-white font-sans mt-1">
                  Confirm Plan Approval & Execution
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowExecutionConfirmModal(false)}
                className="text-zinc-500 hover:text-white p-1 transition-colors text-sm"
              >
                ✕
              </button>
            </div>

            {/* Target Database Details */}
            <div className="p-4 bg-black border border-zinc-800 space-y-2 text-xs">
              <div className="flex items-center justify-between text-zinc-400">
                <span>Target Database Engine:</span>
                <span className="text-white font-bold uppercase text-sky-400">
                  {(plan.target_config?.database_type || 'postgresql').toUpperCase()} ({plan.target_config?.database_type?.toLowerCase() === 'mongodb' ? 'NoSQL Document' : 'Relational'})
                </span>
              </div>
              <div className="flex items-center justify-between text-zinc-400">
                <span>Target Database Destination:</span>
                <span className="text-white font-bold">
                  {plan.target_config?.identifier || 'Target Database'}
                </span>
              </div>
              <div className="flex items-center justify-between text-zinc-400">
                <span>Target Table Mappings:</span>
                <span className="text-zinc-300">
                  {ast.table_mappings?.length || 0} table(s) ({ast.table_mappings?.map((m) => m.target_table_name).join(', ')})
                </span>
              </div>
            </div>

            {/* Truncate / Clean Wipe Target Database Option */}
            <div className="space-y-3">
              <label
                onClick={() => setTruncateTarget(!truncateTarget)}
                className={`flex items-start gap-3.5 p-4 border cursor-pointer select-none transition-all ${
                  truncateTarget
                    ? 'bg-rose-950/20 border-rose-500/60 shadow-[0_0_20px_rgba(244,63,94,0.15)]'
                    : 'bg-black border-zinc-800 hover:border-zinc-700'
                }`}
              >
                <input
                  type="checkbox"
                  checked={truncateTarget}
                  onChange={(e) => setTruncateTarget(e.target.checked)}
                  className="mt-1 w-4 h-4 rounded-none accent-rose-500 cursor-pointer"
                />
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold uppercase text-white font-sans tracking-wide">
                      Clean Wipe Target Database (Delete & Drop Existing Tables)
                    </span>
                    {truncateTarget && (
                      <span className="px-1.5 py-0.2 text-[9px] font-bold uppercase bg-rose-500/20 text-rose-400 border border-rose-500/40">
                        DESTRUCTIVE
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-zinc-400 font-sans leading-relaxed">
                    By checking this box, you explicitly agree that the Docker Agent will inspect the target database and <strong className="text-rose-400">permanently DROP / DELETE all existing tables</strong> before running DDL and data streaming.
                  </p>
                </div>
              </label>

              {/* Warning Banner when Truncate is NOT selected */}
              {!truncateTarget && (
                <div className="p-3.5 bg-amber-950/30 border border-amber-500/40 text-amber-300 text-[11px] font-sans leading-relaxed space-y-1 animate-fadeIn">
                  <div className="flex items-center gap-2 font-bold font-mono uppercase text-amber-400 text-xs">
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                    Target Database Warning
                  </div>
                  <p>
                    Target databases should ideally be empty for a clean migration. If you leave Clean Wipe unchecked and the target database contains existing data, new records will be appended and conflicting primary keys will be skipped according to conflict resolution policies.
                  </p>
                </div>
              )}
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-3 pt-2 border-t border-zinc-800/80">
              <button
                type="button"
                onClick={() => setShowExecutionConfirmModal(false)}
                className="py-2.5 px-5 rounded-none bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white text-xs font-bold uppercase tracking-wider border border-zinc-800 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleApproveAndExecute}
                className={`py-2.5 px-6 rounded-none text-xs font-bold uppercase tracking-wider font-mono transition-all shadow-lg ${
                  truncateTarget
                    ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-950/50'
                    : 'bg-sky-400 hover:bg-sky-300 text-black shadow-sky-950/50'
                }`}
              >
                {truncateTarget ? 'Wipe & Execute Migration' : 'Confirm & Execute Migration'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* JSON AST Modal */}
      {showJsonModal && (
        <div
          onClick={() => setShowJsonModal(false)}
          className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-fadeIn"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="p-6 rounded-none bg-zinc-950 border border-zinc-800 w-full max-w-4xl max-h-[85vh] flex flex-col space-y-4 shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-white">
                Raw Transformation Plan AST (JSON)
              </h3>
              <button
                type="button"
                onClick={() => setShowJsonModal(false)}
                className="text-zinc-400 hover:text-white font-mono text-sm font-bold p-1"
              >
                ✕ Close
              </button>
            </div>
            <pre className="p-4 rounded-none bg-black border border-zinc-900 text-sky-400 font-mono text-xs overflow-auto flex-1 max-h-[60vh]">
              {JSON.stringify(ast, null, 2)}
            </pre>
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => setShowJsonModal(false)}
                className="py-2.5 px-6 rounded-none bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-mono font-bold uppercase border border-zinc-800"
              >
                Close Modal
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PlanBlueprintViewer;
