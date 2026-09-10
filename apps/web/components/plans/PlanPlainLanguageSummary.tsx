import React from 'react';
import { TransformationPlanAST, TableMappingSpec } from '../../types/migrationPlan';

interface PlanPlainLanguageSummaryProps {
  ast: TransformationPlanAST;
}

// Builds a plain-English description of one table mapping using only
// fields already present in the AST -- no new backend data required.
function describeTableMapping(tm: TableMappingSpec): string {
  const sourceList = tm.source_tables
    .map((s) => `${s.identifier}.${s.table_name}`)
    .join(' and ');

  const confidencePct = Math.round((tm.confidence_score || 0) * 100);

  if (tm.transformation_type === 'direct_copy') {
    return `${tm.target_table_name} will be copied directly from ${sourceList}. (${confidencePct}% confidence)`;
  }

  if (tm.transformation_type === 'merge') {
    const dedupKey = tm.conflict_resolution?.deduplication_key;
    const dedupStrategy = tm.conflict_resolution?.deduplication_strategy;
    const pkStrategy = tm.conflict_resolution?.primary_key_strategy;

    let sentence = `${tm.target_table_name} will be built by merging ${sourceList}`;
    if (dedupKey) {
      sentence += `, matching records on ${dedupKey}`;
    }
    sentence += '.';

    if (dedupStrategy === 'last_updated_wins') {
      sentence += ' When the same record appears in more than one source, the most recently updated version will be kept.';
    } else if (dedupStrategy === 'first_wins') {
      sentence += ' When the same record appears in more than one source, the first one encountered will be kept.';
    } else if (dedupStrategy === 'merge_all') {
      sentence += ' Fields from all matching records will be combined into one.';
    }

    if (pkStrategy === 'uuid_v4_rekey') {
      sentence += ' Each merged record will be assigned a brand-new random ID, since the original IDs from each source could collide.';
    } else if (pkStrategy === 'prefix_id') {
      sentence += ' Original IDs will be kept but prefixed per source to avoid collisions.';
    } else if (pkStrategy === 'autoincrement_offset') {
      sentence += ' Original numeric IDs will be offset per source to avoid collisions.';
    } else if (pkStrategy === 'keep_original') {
      sentence += ' Original IDs will be preserved as-is.';
    }

    sentence += ` (${confidencePct}% confidence)`;
    return sentence;
  }

  if (tm.transformation_type === 'split_target') {
    return `${sourceList} will be split across multiple target tables, including ${tm.target_table_name}. (${confidencePct}% confidence)`;
  }

  return `${tm.target_table_name} will be created from ${sourceList}. (${confidencePct}% confidence)`;
}

export const PlanPlainLanguageSummary: React.FC<PlanPlainLanguageSummaryProps> = ({ ast }) => {
  if (!ast?.table_mappings || ast.table_mappings.length === 0) return null;

  return (
    <div className="p-5 bg-zinc-950 border border-zinc-800 space-y-3">
      <h3 className="text-sm font-bold text-white uppercase font-sans tracking-wide">
        What this migration plan will do
      </h3>
      <ul className="space-y-2">
        {ast.table_mappings.map((tm) => (
          <li key={tm.target_table_name} className="text-xs text-zinc-300 leading-relaxed font-mono flex gap-2">
            <span className="text-sky-400">→</span>
            <span>{describeTableMapping(tm)}</span>
          </li>
        ))}
      </ul>
      {ast.warnings && ast.warnings.length > 0 && (
        <div className="pt-2 border-t border-zinc-900 space-y-1.5">
          {ast.warnings.map((w, i) => (
            <p key={i} className="text-xs text-amber-400 leading-relaxed font-mono flex gap-2">
              <span>⚠</span>
              <span>{w}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  );
};

export default PlanPlainLanguageSummary;
