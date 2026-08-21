'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import planService from '../../services/planService';

interface GeneratePlanActionProps {
  agentId: string;
}

export const GeneratePlanAction: React.FC<GeneratePlanActionProps> = ({ agentId }) => {
  const router = useRouter();
  const [targetType, setTargetType] = useState<string>('postgresql');
  const [customInstructions, setCustomInstructions] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleGeneratePlan = async () => {
    if (!agentId) return;

    setIsGenerating(true);
    setErrorMsg(null);

    try {
      const plan = await planService.createPlan(agentId, {
        database_type: targetType,
        custom_instructions: customInstructions.trim() || undefined,
      });

      // Redirect to Transformation Blueprint view with generated planId
      router.push(`/transformation-plan?planId=${plan.id}`);
    } catch (err: any) {
      const msg =
        err.response?.data?.detail ||
        err.message ||
        'Failed to generate migration plan. Ensure Agent has completed schema introspection.';
      setErrorMsg(msg);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="p-6 rounded-none bg-black border border-sky-400/40 backdrop-blur-xl space-y-6 shadow-[0_0_25px_rgba(56,189,248,0.15)] relative overflow-hidden">
      {/* Background Accent Grid */}
      <div className="absolute inset-0 bg-[radial-gradient(#38bdf8_1px,transparent_1px)] [background-size:16px_16px] opacity-5 pointer-events-none" />

      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
        <div>
          <span className="text-[10px] font-mono font-bold tracking-widest px-2.5 py-0.5 rounded-none uppercase bg-sky-400/10 text-sky-400 border border-sky-400/30">
            AI PLANNING ENGINE
          </span>
          <h3 className="text-xl font-extrabold text-white uppercase font-sans tracking-wide mt-1">
            Generate Migration Transformation Blueprint
          </h3>
          <p className="text-zinc-400 text-xs max-w-2xl mt-1 leading-relaxed">
            The AI Planning Engine will analyze all profiled source schema tables, primary keys, foreign keys, and data types to construct an executable transformation AST.
          </p>
        </div>
      </div>

      {errorMsg && (
        <div className="p-4 rounded-none bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-mono">
          🚨 {errorMsg}
        </div>
      )}

      <div className="space-y-2">
        <label className="block text-[10px] font-mono font-semibold uppercase tracking-wider text-zinc-300">
          Custom AI Guidance / Tuning Instructions (Optional)
        </label>
        <input
          type="text"
          value={customInstructions}
          onChange={(e) => setCustomInstructions(e.target.value)}
          placeholder="e.g. Prefer UUID primary keys, map created_on to created_at, convert enum ints to text"
          className="w-full px-4 py-3 rounded-none bg-zinc-950 border border-zinc-800 text-white text-xs placeholder-zinc-600 focus:outline-none focus:border-sky-400 font-sans transition-colors"
        />
      </div>

      <div className="flex items-center justify-end pt-2">
        <button
          type="button"
          onClick={handleGeneratePlan}
          disabled={isGenerating}
          className="w-full sm:w-auto inline-flex items-center justify-center gap-3 py-3.5 px-10 rounded-none bg-sky-400 hover:bg-sky-300 text-black text-xs font-bold uppercase tracking-wider transition-all shadow-lg shadow-sky-950/50 hover:scale-[1.01] disabled:opacity-50"
        >
          {isGenerating ? (
            <>
              <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-none animate-spin" />
              <span>Constructing AI Blueprint AST...</span>
            </>
          ) : (
            <>
              <span>GENERATE AI MIGRATION PLAN</span>
              <span className="text-base">→</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default GeneratePlanAction;
