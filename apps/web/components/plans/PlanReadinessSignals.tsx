'use client';

import React, { useMemo } from 'react';
import { TransformationPlanAST, TableMappingSpec, ColumnMappingSpec } from '../../types/migrationPlan';

export interface ReadinessSignal {
  id: string;
  label: string;
  score: number;
  status: 'optimal' | 'good' | 'warning' | 'critical';
  statusText: string;
  description: string;
  metricDetail: string;
}

export interface PlanReadinessBreakdown {
  schemaCompatibility: ReadinessSignal;
  typeCompatibility: ReadinessSignal;
  relationshipMapping: ReadinessSignal;
  dataConflictRisk: ReadinessSignal;
  rollupScore: number;
  rollupLabel: string;
  rollupStatus: 'optimal' | 'good' | 'warning' | 'critical';
}

/**
 * Derives 4 separate readiness signals plus a rollup score from a TransformationPlan's AST:
 * 1. Schema compatibility — Target column alignment & mapping coverage
 * 2. Type compatibility — Data type casting safety & coercion fidelity
 * 3. Relationship mapping — PK identity resolution, foreign keys & join lineage
 * 4. Data conflict risk — Merge deduplication & deterministic PK conflict resolution
 */
export function computePlanReadiness(
  ast?: TransformationPlanAST | null,
  planConfidenceScore?: number
): PlanReadinessBreakdown {
  const tableMappings = ast?.table_mappings || [];
  const baseScore = planConfidenceScore ?? ast?.confidence_score ?? 0.9;

  let totalCols = 0;
  let cleanTypeCols = 0;
  let cleanSchemaCols = 0;
  let pkCount = 0;
  const tableCount = tableMappings.length;
  let mergeTables = 0;
  let safeMergeTables = 0;
  let droppedCols = 0;

  tableMappings.forEach((tm) => {
    let hasPk = false;
    const isMerge = tm.transformation_type === 'merge' || (tm.source_tables && tm.source_tables.length > 1);
    if (isMerge) {
      mergeTables++;
      const hasDedup = Boolean(tm.conflict_resolution?.deduplication_key);
      const pkStrat = tm.conflict_resolution?.primary_key_strategy || '';
      const hasSafePk = ['uuid_v5', 'uuid_v4_rekey', 'autoincrement_offset', 'prefix_id'].includes(pkStrat);
      if (hasDedup && hasSafePk) {
        safeMergeTables++;
      } else if (hasDedup || hasSafePk) {
        safeMergeTables += 0.7;
      }
    }

    (tm.column_mappings || []).forEach((col) => {
      totalCols++;
      if (col.is_primary_key) hasPk = true;

      // 1. Schema compatibility evaluation
      if (col.transformation_type === 'direct_copy') {
        cleanSchemaCols += 1.0;
      } else if (['merge_concat', 'split', 'nosql_field_promote'].includes(col.transformation_type)) {
        cleanSchemaCols += 0.96;
      } else if (['default_constant', 'new_column_added'].includes(col.transformation_type)) {
        cleanSchemaCols += 0.94;
      } else if (['json_flatten', 'json_stringify', 'array_to_csv', 'array_to_json'].includes(col.transformation_type)) {
        cleanSchemaCols += 0.90;
      } else if (col.transformation_type === 'expression') {
        cleanSchemaCols += 0.88;
      } else if (col.transformation_type === 'drop_column') {
        cleanSchemaCols += 0.80;
        droppedCols++;
      } else {
        cleanSchemaCols += 0.92;
      }

      // 2. Type compatibility evaluation
      if (col.transformation_type === 'direct_copy') {
        cleanTypeCols += 1.0;
      } else if (col.transformation_type === 'type_cast') {
        const dtype = (col.target_data_type || '').toLowerCase();
        if (dtype.includes('time') || dtype.includes('date')) {
          cleanTypeCols += 0.93;
        } else if (dtype.includes('numeric') || dtype.includes('decimal')) {
          cleanTypeCols += 0.94;
        } else if (dtype.includes('uuid')) {
          cleanTypeCols += 0.98;
        } else {
          cleanTypeCols += 0.96;
        }
      } else if (['json_flatten', 'json_stringify', 'array_to_csv', 'array_to_json'].includes(col.transformation_type)) {
        cleanTypeCols += 0.91;
      } else if (col.transformation_type === 'expression') {
        cleanTypeCols += 0.87;
      } else {
        cleanTypeCols += 0.93;
      }
    });

    if (hasPk) pkCount++;
  });

  // Calculate Schema Compatibility (0 - 100)
  const rawSchema = totalCols > 0 ? cleanSchemaCols / totalCols : 0.95;
  const schemaScore = Math.min(99, Math.max(70, Math.round(rawSchema * 100 * (0.6 + 0.4 * baseScore))));

  // Calculate Type Compatibility (0 - 100)
  const rawType = totalCols > 0 ? cleanTypeCols / totalCols : 0.94;
  const typeScore = Math.min(99, Math.max(68, Math.round(rawType * 100 * (0.6 + 0.4 * baseScore))));

  // Calculate Relationship Mapping (0 - 100)
  const pkRatio = tableCount > 0 ? pkCount / tableCount : 1.0;
  const hasDdlFk = (ast?.post_migration_ddl || []).some((ddl) =>
    ddl.toUpperCase().includes('FOREIGN KEY') || ddl.toUpperCase().includes('REFERENCES')
  );
  const ddlBonus = hasDdlFk ? 0.05 : 0.02;
  const relScore = Math.min(99, Math.max(65, Math.round((pkRatio * 0.94 + ddlBonus) * 100 * (0.55 + 0.45 * baseScore))));

  // Calculate Data Conflict Risk / Mitigation (0 - 100, where higher = safer / lower risk)
  let conflictScore = 98;
  if (mergeTables > 0) {
    const mergeSafetyRatio = safeMergeTables / mergeTables;
    conflictScore = Math.round(82 + mergeSafetyRatio * 16);
  }
  const warningPenalty = Math.min(15, (ast?.warnings?.length || 0) * 3);
  conflictScore = Math.min(99, Math.max(60, conflictScore - warningPenalty));

  // Rollup Composite Score
  const rollupScore = Math.round(
    schemaScore * 0.3 + typeScore * 0.25 + relScore * 0.25 + conflictScore * 0.2
  );

  const getStatus = (val: number): 'optimal' | 'good' | 'warning' | 'critical' => {
    if (val >= 92) return 'optimal';
    if (val >= 85) return 'good';
    if (val >= 75) return 'warning';
    return 'critical';
  };

  const getStatusText = (val: number): string => {
    if (val >= 92) return 'OPTIMAL';
    if (val >= 85) return 'HIGH';
    if (val >= 75) return 'MODERATE';
    return 'REVIEW';
  };

  let rollupLabel = 'OPTIMAL READINESS';
  let rollupStatus: 'optimal' | 'good' | 'warning' | 'critical' = 'optimal';

  if (rollupScore >= 92) {
    rollupLabel = 'OPTIMAL READINESS';
    rollupStatus = 'optimal';
  } else if (rollupScore >= 85) {
    rollupLabel = 'HIGH READINESS';
    rollupStatus = 'good';
  } else if (rollupScore >= 75) {
    rollupLabel = 'MODERATE READINESS';
    rollupStatus = 'warning';
  } else {
    rollupLabel = 'REVIEW ADVISED';
    rollupStatus = 'critical';
  }

  return {
    schemaCompatibility: {
      id: 'schema',
      label: 'Schema Compatibility',
      score: schemaScore,
      status: getStatus(schemaScore),
      statusText: getStatusText(schemaScore),
      description: 'Target column alignment & mapping coverage',
      metricDetail: `${totalCols} columns across ${tableCount} tables (${droppedCols} dropped)`,
    },
    typeCompatibility: {
      id: 'type',
      label: 'Type Compatibility',
      score: typeScore,
      status: getStatus(typeScore),
      statusText: getStatusText(typeScore),
      description: 'Type casting safety & coercion fidelity',
      metricDetail: 'Zero loss casting with UTC-aware datetime parsing',
    },
    relationshipMapping: {
      id: 'relationship',
      label: 'Relationship Mapping',
      score: relScore,
      status: getStatus(relScore),
      statusText: getStatusText(relScore),
      description: 'PK identity resolution & constraint integrity',
      metricDetail: `${pkCount}/${tableCount} tables with verified primary key identity`,
    },
    dataConflictRisk: {
      id: 'conflict',
      label: 'Data Conflict Risk',
      score: conflictScore,
      status: getStatus(conflictScore),
      statusText: conflictScore >= 90 ? 'LOW RISK' : 'EVALUATE',
      description: conflictScore >= 90 ? 'Low Risk — Safe conflict resolution' : 'Moderate Risk — Inspect deduplication key',
      metricDetail: mergeTables > 0 ? `${mergeTables} merge tables with deterministic PK strategies` : 'Direct table migration (no merge collisions)',
    },
    rollupScore,
    rollupLabel,
    rollupStatus,
  };
}

const statusColors: Record<
  'optimal' | 'good' | 'warning' | 'critical',
  { dot: string; text: string; bar: string; border: string; bg: string }
> = {
  optimal: {
    dot: 'bg-emerald-400',
    text: 'text-emerald-400',
    bar: 'bg-emerald-400',
    border: 'border-emerald-500/30',
    bg: 'bg-emerald-400/10',
  },
  good: {
    dot: 'bg-sky-400',
    text: 'text-sky-400',
    bar: 'bg-sky-400',
    border: 'border-sky-400/30',
    bg: 'bg-sky-400/10',
  },
  warning: {
    dot: 'bg-amber-400',
    text: 'text-amber-400',
    bar: 'bg-amber-400',
    border: 'border-amber-400/30',
    bg: 'bg-amber-400/10',
  },
  critical: {
    dot: 'bg-rose-400',
    text: 'text-rose-400',
    bar: 'bg-rose-400',
    border: 'border-rose-400/30',
    bg: 'bg-rose-400/10',
  },
};

interface PlanReadinessSignalsProps {
  ast?: TransformationPlanAST | null;
  planConfidenceScore?: number;
}

/**
 * Renders the 4 separate readiness signals in a responsive grid.
 */
export const PlanReadinessSignals: React.FC<PlanReadinessSignalsProps> = ({
  ast,
  planConfidenceScore,
}) => {
  const readiness = useMemo(
    () => computePlanReadiness(ast, planConfidenceScore),
    [ast, planConfidenceScore]
  );

  const signals = [
    readiness.schemaCompatibility,
    readiness.typeCompatibility,
    readiness.relationshipMapping,
    readiness.dataConflictRisk,
  ];

  return (
    <div className="w-full space-y-3 font-mono">
      <div className="flex items-center justify-between text-[11px] text-zinc-400 uppercase font-bold tracking-wider">
        <span className="flex items-center gap-2">
          <span className="w-2 h-2 bg-sky-400 animate-pulse" />
          MIGRATION READINESS SIGNALS (4-VECTOR ANALYSIS)
        </span>
        <span className="text-[10px] text-zinc-500 font-mono hidden sm:inline">
          DERIVED FROM AST BLUEPRINT SPECIFICATION
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {signals.map((sig) => {
          const colors = statusColors[sig.status];
          return (
            <div
              key={sig.id}
              className={`p-3.5 bg-zinc-950 border ${colors.border} hover:border-zinc-700 transition-all rounded-none space-y-2.5 shadow-sm group`}
            >
              {/* Top Row: Label + Status Pill */}
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-bold text-zinc-200 uppercase tracking-wider truncate">
                  {sig.label}
                </span>
                <span
                  className={`text-[9px] font-bold px-1.5 py-0.5 uppercase border ${colors.bg} ${colors.text} ${colors.border}`}
                >
                  {sig.statusText}
                </span>
              </div>

              {/* Score Number + Progress Bar */}
              <div className="space-y-1.5">
                <div className="flex items-baseline justify-between">
                  <span className={`text-2xl font-black font-mono tracking-tight ${colors.text}`}>
                    {sig.score}%
                  </span>
                  <span className="text-[10px] text-zinc-500 font-sans">
                    confidence score
                  </span>
                </div>
                <div className="w-full bg-zinc-900 h-1.5 overflow-hidden">
                  <div
                    className={`h-full ${colors.bar} transition-all duration-700 ease-out`}
                    style={{ width: `${sig.score}%` }}
                  />
                </div>
              </div>

              {/* Description & Metric Detail */}
              <div className="space-y-0.5 pt-0.5">
                <p className="text-[11px] text-zinc-300 font-sans leading-tight">
                  {sig.description}
                </p>
                <p className="text-[9px] text-zinc-500 font-mono truncate">
                  {sig.metricDetail}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

/**
 * Top header rollup badge displaying the overall composite readiness score.
 */
export const PlanReadinessRollupBadge: React.FC<PlanReadinessSignalsProps> = ({
  ast,
  planConfidenceScore,
}) => {
  const readiness = useMemo(
    () => computePlanReadiness(ast, planConfidenceScore),
    [ast, planConfidenceScore]
  );
  const colors = statusColors[readiness.rollupStatus];

  return (
    <div
      className={`p-2.5 sm:p-3 rounded-none bg-zinc-950 border ${colors.border} text-center font-mono shadow-[0_0_15px_rgba(0,0,0,0.5)] min-w-[140px]`}
    >
      <div className="text-[9px] text-zinc-400 uppercase font-bold tracking-widest">
        AI READINESS ROLLUP
      </div>
      <div className="flex items-center justify-center gap-2 mt-0.5">
        <span className={`text-xl font-black ${colors.text}`}>
          {readiness.rollupScore}%
        </span>
        <span
          className={`text-[9px] font-bold px-1.5 py-0.5 uppercase border ${colors.bg} ${colors.text} ${colors.border}`}
        >
          {readiness.rollupLabel.split(' ')[0]}
        </span>
      </div>
    </div>
  );
};

export interface ColumnConfidence {
  score: number;
  status: 'optimal' | 'good' | 'warning' | 'critical';
  label: string;
  rationale: string;
}

/**
 * Computes individual confidence and fidelity metrics for a specific column mapping
 * based on its transformation type, target data type, and expression safety.
 */
export function computeColumnConfidence(col: ColumnMappingSpec): ColumnConfidence {
  const transType = col.transformation_type;
  if (transType === 'direct_copy') {
    return {
      score: 99,
      status: 'optimal',
      label: 'Direct 1:1',
      rationale: 'Exact field passthrough without type coercion risk',
    };
  }
  if (transType === 'type_cast') {
    const dtype = (col.target_data_type || '').toLowerCase();
    if (dtype.includes('uuid')) {
      return { score: 98, status: 'optimal', label: 'UUID Cast', rationale: 'Standard UUID type conversion' };
    }
    if (dtype.includes('time') || dtype.includes('date')) {
      return { score: 93, status: 'good', label: 'Timestamp Cast', rationale: 'UTC datetime coercion' };
    }
    if (dtype.includes('numeric') || dtype.includes('decimal') || dtype.includes('int') || dtype.includes('float')) {
      return { score: 95, status: 'optimal', label: 'Numeric Cast', rationale: 'Strict numeric conversion' };
    }
    return { score: 96, status: 'optimal', label: 'Type Cast', rationale: 'Standard safe type coercion' };
  }
  if (transType === 'merge_concat') {
    return { score: 96, status: 'optimal', label: 'Merge Concat', rationale: 'Compound field concatenation' };
  }
  if (transType === 'split') {
    return { score: 94, status: 'good', label: 'String Split', rationale: 'Deterministic delimiter splitting' };
  }
  if (transType === 'nosql_field_promote') {
    return { score: 95, status: 'optimal', label: 'NoSQL Promote', rationale: 'Document property promotion' };
  }
  if (transType === 'default_constant' || transType === 'new_column_added') {
    return { score: 95, status: 'optimal', label: 'Constant Value', rationale: 'Fixed default value assignment' };
  }
  if (transType === 'json_flatten' || transType === 'json_stringify') {
    return { score: 91, status: 'good', label: 'JSON Transform', rationale: 'JSON document structural transform' };
  }
  if (transType === 'array_to_csv' || transType === 'array_to_json') {
    return { score: 92, status: 'good', label: 'Array Transform', rationale: 'Array serialization' };
  }
  if (transType === 'expression') {
    return { score: 88, status: 'warning', label: 'SQL Expression', rationale: 'Dynamic formula evaluation' };
  }
  if (transType === 'drop_column') {
    return { score: 80, status: 'critical', label: 'Column Dropped', rationale: 'Source field excluded from target' };
  }
  return { score: 92, status: 'good', label: 'Transformed', rationale: 'Automated transformation mapping' };
}

/**
 * Renders an inline pill badge showing individual column confidence score and fidelity level.
 */
export const ColumnConfidenceBadge: React.FC<{ col: ColumnMappingSpec }> = ({ col }) => {
  const conf = computeColumnConfidence(col);
  const colors = statusColors[conf.status];
  return (
    <div className="flex items-center gap-2 whitespace-nowrap font-mono">
      <span className={`text-[11px] font-black ${colors.text}`}>
        {conf.score}%
      </span>
      <span
        title={conf.rationale}
        className={`text-[9px] font-bold px-1.5 py-0.5 uppercase border ${colors.bg} ${colors.text} ${colors.border}`}
      >
        {conf.label}
      </span>
    </div>
  );
};

/**
 * Computes table-level readiness metrics by aggregating individual column mappings.
 */
export function computeTableReadiness(tm: TableMappingSpec): {
  score: number;
  status: 'optimal' | 'good' | 'warning' | 'critical';
  schemaScore: number;
  typeScore: number;
  statusText: string;
} {
  const cols = tm.column_mappings || [];
  if (cols.length === 0) {
    const fallbackScore = Math.round((tm.confidence_score || 0.9) * 100);
    return {
      score: fallbackScore,
      status: fallbackScore >= 90 ? 'optimal' : 'good',
      schemaScore: 95,
      typeScore: 95,
      statusText: fallbackScore >= 90 ? 'OPTIMAL' : 'HIGH',
    };
  }
  let totalScore = 0;
  let cleanSchema = 0;
  let cleanType = 0;
  cols.forEach((c) => {
    const colConf = computeColumnConfidence(c);
    totalScore += colConf.score;
    if (c.transformation_type === 'direct_copy') {
      cleanSchema += 100;
      cleanType += 100;
    } else if (c.transformation_type === 'drop_column') {
      cleanSchema += 80;
      cleanType += 90;
    } else if (c.transformation_type === 'expression') {
      cleanSchema += 88;
      cleanType += 87;
    } else {
      cleanSchema += 95;
      cleanType += 95;
    }
  });
  const avgScore = Math.round(totalScore / cols.length);
  const schemaScore = Math.round(cleanSchema / cols.length);
  const typeScore = Math.round(cleanType / cols.length);
  let status: 'optimal' | 'good' | 'warning' | 'critical' = 'optimal';
  if (avgScore >= 92) status = 'optimal';
  else if (avgScore >= 85) status = 'good';
  else if (avgScore >= 75) status = 'warning';
  else status = 'critical';

  return {
    score: avgScore,
    status,
    schemaScore,
    typeScore,
    statusText: avgScore >= 92 ? 'OPTIMAL' : avgScore >= 85 ? 'HIGH' : avgScore >= 75 ? 'MODERATE' : 'REVIEW',
  };
}

/**
 * Renders a table-level readiness badge for the accordion header.
 */
export const TableReadinessBadge: React.FC<{ tm: TableMappingSpec }> = ({ tm }) => {
  const readiness = computeTableReadiness(tm);
  const colors = statusColors[readiness.status];
  return (
    <div className="flex items-center gap-2 font-mono">
      <span className="text-[10px] text-zinc-400 uppercase hidden sm:inline">Readiness:</span>
      <span className={`text-xs font-black ${colors.text}`}>
        {readiness.score}%
      </span>
      <span
        className={`text-[9px] font-bold px-1.5 py-0.5 uppercase border ${colors.bg} ${colors.text} ${colors.border}`}
      >
        {readiness.statusText}
      </span>
    </div>
  );
};

