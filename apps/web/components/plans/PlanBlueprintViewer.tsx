'use client';

import React, { useState, useRef } from 'react';
import { PlanDetailResponse, ColumnMappingSpec, TransformationPlanAST } from '../../types/migrationPlan';
import { ExecutionJobResponse } from '../../types/execution';
import planService from '../../services/planService';
import executionService from '../../services/executionService';
import PlanDiagramViewer from './PlanDiagramViewer';
import JobExecutionBanner from './JobExecutionBanner';
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

  // Agent Execution State
  const [activeJob, setActiveJob] = useState<ExecutionJobResponse | null>(null);
  const [isApproving, setIsApproving] = useState<boolean>(false);

  // Refinement Prompt State
  const [refinementPrompt, setRefinementPrompt] = useState<string>('');
  const [isRefining, setIsRefining] = useState<boolean>(false);
  const [showJsonModal, setShowJsonModal] = useState<boolean>(false);
  const [expandedTable, setExpandedTable] = useState<string | null>(
    initialPlan.plan_data?.table_mappings?.[0]?.target_table_name || null
  );

  const ast = isEditing ? editableAst : plan.plan_data;
  const isApproved = plan.status === 'completed' || plan.status === 'approved';

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

  // Handle Natural Language AI Plan Refinement (LLM Re-review)
  const handleRefinePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!refinementPrompt.trim() || isRefining) return;

    setIsRefining(true);
    try {
      const updated = await planService.refinePlan(plan.id, refinementPrompt.trim());
      setPlan(updated);
      setEditableAst(updated.plan_data);
      setRefinementPrompt('');

      if (updated.is_valid) {
        toast.success('LLM re-reviewed & refined blueprint successfully!');
      } else {
        toast.error('LLM refinement generated schema feasibility errors! Review diagnostic alert below.');
        scrollToDiagnostics();
      }
      if (onPlanUpdated) onPlanUpdated(updated);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to refine plan.';
      toast.error(`Refinement Error: ${msg}`);
      
      const errDetails = err.response?.data?.detail;
      const errorList = typeof errDetails === 'string' ? [errDetails] : ['Requested LLM refinement is not feasible with available database schemas.'];
      setPlan((prev) => ({
        ...prev,
        is_valid: false,
        status: 'invalid_edits',
        validation_errors: {
          is_valid: false,
          errors: errorList,
          warnings: [],
          explanation: `LLM Refinement could not be completed: ${msg}`,
        },
      }));
      scrollToDiagnostics();
    } finally {
      setIsRefining(false);
    }
  };

  // Handle Plan Approval & Agent Job Dispatch
  const handleApproveAndExecute = async () => {
    if (isApproving) return;

    if (!plan.is_valid) {
      toast.error('Cannot execute invalid plan! Fix schema feasibility errors first.');
      scrollToDiagnostics();
      return;
    }

    setIsApproving(true);
    try {
      // 1. Approve Plan
      const approved = await planService.approvePlan(plan.id);
      setPlan(approved);

      // 2. Trigger Execution Job on Docker Agent
      const job = await executionService.startPlanExecution(plan.id);
      setActiveJob(job);

      toast.success('Plan approved! Data migration job queued on Docker Agent.');
      if (onPlanUpdated) onPlanUpdated(approved);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to execute plan.';
      toast.error(`Execution Error: ${msg}`);
      scrollToDiagnostics();
    } finally {
      setIsApproving(false);
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
            <div className="p-3 rounded-none bg-zinc-950 border border-sky-400/30 text-center font-mono">
              <div className="text-[10px] text-zinc-500 uppercase font-bold">AI CONFIDENCE</div>
              <div className="text-lg font-bold text-sky-400">{confidencePercentage}%</div>
            </div>
            <button
              type="button"
              onClick={() => setShowJsonModal(true)}
              className="py-3 px-4 rounded-none bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-mono font-bold uppercase tracking-wider border border-zinc-800 transition-colors"
            >
              View JSON AST
            </button>
          </div>
        </div>

        {/* Controls Bar: View Mode Switcher + Edit Toggle */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-2 border-b border-zinc-900 pb-3">
          <div className="flex items-center gap-3">
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
          </div>
        )}
      </div>

      {/* Live Agent Execution Progress Banner (if active) */}
      {activeJob && (
        <JobExecutionBanner
          job={activeJob}
          onJobUpdated={(updated) => setActiveJob(updated)}
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
                                updated.table_mappings[tmIdx].transformation_type = e.target.value;
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
                      <span>Confidence: <strong className="text-sky-400">{Math.round(tm.confidence_score * 100)}%</strong></span>
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
                                        updated.table_mappings[tmIdx].conflict_resolution = { deduplication_key: '', primary_key_strategy: 'uuid_v5' };
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
                                        updated.table_mappings[tmIdx].conflict_resolution = { deduplication_key: '', primary_key_strategy: 'uuid_v5' };
                                      }
                                      updated.table_mappings[tmIdx].conflict_resolution!.primary_key_strategy = e.target.value;
                                    }
                                    setEditableAst(updated);
                                  }}
                                  className="px-2 py-0.5 bg-zinc-900 border border-sky-400 text-sky-400 font-mono text-xs uppercase"
                                >
                                  <option value="uuid_v5">uuid_v5</option>
                                  <option value="uuid_v4_rekey">uuid_v4_rekey</option>
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
              value={refinementPrompt}
              onChange={(e) => setRefinementPrompt(e.target.value)}
              placeholder="e.g. Map user_id to account_uuid and convert status int enum to string varchar"
              className="flex-1 px-4 py-3 rounded-none bg-zinc-950 border border-zinc-800 text-white text-xs placeholder-zinc-600 focus:outline-none focus:border-sky-400 font-sans transition-colors"
            />
            <button
              type="submit"
              disabled={isRefining}
              className="py-3 px-6 rounded-none bg-sky-400 hover:bg-sky-300 text-black text-xs font-bold uppercase tracking-wider transition-colors shadow-lg shadow-sky-950/50 disabled:opacity-50 whitespace-nowrap font-mono"
            >
              {isRefining ? 'Re-reviewing with LLM...' : 'Refine with LLM'}
            </button>
          </div>
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

        <button
          type="button"
          onClick={handleApproveAndExecute}
          disabled={isApproving || isApproved}
          className={`py-3.5 px-10 rounded-none text-xs font-bold font-mono uppercase tracking-wider transition-all shadow-lg ${
            isApproved
              ? 'bg-emerald-500 text-black cursor-default'
              : 'bg-sky-400 hover:bg-sky-300 text-black shadow-sky-950/50 hover:scale-[1.01]'
          } disabled:opacity-50`}
        >
          {isApproved ? 'PLAN APPROVED ✓' : isApproving ? 'Executing on Agent...' : 'APPROVE & EXECUTE MIGRATION'}
        </button>
      </div>

      {/* JSON AST Modal */}
      {showJsonModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="p-6 rounded-none bg-zinc-950 border border-zinc-800 w-full max-w-4xl max-h-[85vh] flex flex-col space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-white">
                Raw Transformation Plan AST (JSON)
              </h3>
              <button
                type="button"
                onClick={() => setShowJsonModal(false)}
                className="text-zinc-400 hover:text-white font-mono text-sm font-bold"
              >
                ✕
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
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PlanBlueprintViewer;
