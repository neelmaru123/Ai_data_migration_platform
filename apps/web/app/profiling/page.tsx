'use client';

import React, { useState, useEffect } from 'react';
import { AgentDetailResponse } from '../../types/agent';
import agentService from '../../services/agentService';
import AgentStatusBanner from '../../components/agents/AgentStatusBanner';
import SchemaCatalogViewer from '../../components/profiling/SchemaCatalogViewer';
import GeneratePlanAction from '../../components/profiling/GeneratePlanAction';

export default function ProfilingPage() {
  const [agents, setAgents] = useState<AgentDetailResponse[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentDetailResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    agentService
      .listAgents()
      .then((list) => {
        setAgents(list);
        if (list.length > 0) setSelectedAgent(list[0]);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-black text-slate-100 flex flex-col justify-between selection:bg-sky-400 selection:text-black">
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-96 bg-gradient-to-b from-sky-400/15 via-sky-500/5 to-transparent blur-3xl pointer-events-none -z-10" />

      <main className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 flex-1">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-zinc-800 pb-6">
          <div>
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-none text-[11px] font-mono font-bold uppercase tracking-widest bg-sky-400/10 text-sky-400 border border-sky-400/30 mb-2">
              ZERO-DATA CATALOG INTROSPECTION
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight sm:text-4xl uppercase font-sans">
              Database Schema Profiler
            </h1>
            <p className="text-zinc-400 text-xs sm:text-sm max-w-2xl mt-1 leading-relaxed">
              Explore structural metadata snapshots, table schemas, data types, constraints, and relationships.
            </p>
          </div>
        </div>

        {loading ? (
          <div className="p-16 text-center rounded-none bg-black border border-zinc-800 text-zinc-400 font-mono text-xs space-y-3">
            <div className="w-6 h-6 border-2 border-sky-400 border-t-transparent rounded-none animate-spin mx-auto" />
            <p>Loading schema profiling catalogs...</p>
          </div>
        ) : !selectedAgent ? (
          <div className="p-16 text-center rounded-none bg-black border border-zinc-800 space-y-4">
            <h3 className="text-xl font-bold text-white uppercase tracking-wide">No Agents Available</h3>
            <a
              href="/agents/create"
              className="inline-block py-3 px-8 rounded-none bg-sky-400 text-black text-xs font-bold uppercase tracking-wider"
            >
              Create Migration Agent
            </a>
          </div>
        ) : (
          <div className="space-y-8">
            <AgentStatusBanner agent={selectedAgent} />
            {selectedAgent.data_sources && selectedAgent.data_sources.length > 0 && (
              <>
                <SchemaCatalogViewer dataSources={selectedAgent.data_sources} />
                <GeneratePlanAction agentId={selectedAgent.id} />
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
