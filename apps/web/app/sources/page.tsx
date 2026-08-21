'use client';

import React, { useState, useEffect } from 'react';
import { AgentDetailResponse } from '../../types/agent';
import agentService from '../../services/agentService';
import AgentStatusBanner from '../../components/agents/AgentStatusBanner';
import SchemaCatalogViewer from '../../components/profiling/SchemaCatalogViewer';
import GeneratePlanAction from '../../components/profiling/GeneratePlanAction';

export default function SourcesPage() {
  const [agents, setAgents] = useState<AgentDetailResponse[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentDetailResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchAgents = async () => {
    try {
      setLoading(true);
      const list = await agentService.listAgents();
      setAgents(list);
      if (list.length > 0) {
        setSelectedAgent(list[0]);
      }
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const [refreshKey, setRefreshKey] = useState<number>(0);

  return (
    <div className="min-h-screen bg-black text-slate-100 flex flex-col justify-between selection:bg-sky-400 selection:text-black">
      {/* Background Accent Glow */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-96 bg-gradient-to-b from-sky-400/15 via-sky-500/5 to-transparent blur-3xl pointer-events-none -z-10" />

      {/* Main Container */}
      <main className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 flex-1">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-zinc-800 pb-6">
          <div>
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-none text-[11px] font-mono font-bold uppercase tracking-widest bg-sky-400/10 text-sky-400 border border-sky-400/30 mb-2">
              CATALOG PROFILER
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight sm:text-4xl uppercase font-sans">
              Data Sources & Schema Inspection
            </h1>
            <p className="text-zinc-400 text-xs sm:text-sm max-w-2xl mt-1 leading-relaxed">
              Inspect database tables, column types, constraints, and relationships profiled by your agent daemons.
            </p>
          </div>

          <a
            href="/agents/create"
            className="py-3 px-6 rounded-none bg-sky-400 hover:bg-sky-300 text-black text-xs font-bold uppercase tracking-wider transition-colors shadow-lg shadow-sky-950/50"
          >
            + Register New Agent
          </a>
        </div>

        {/* Agent Selector Tabs */}
        {agents.length > 1 && (
          <div className="flex items-center gap-2 border-b border-zinc-800 pb-3 overflow-x-auto">
            <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-zinc-400 mr-2">
              Select Agent:
            </span>
            {agents.map((ag) => (
              <button
                key={ag.id}
                type="button"
                onClick={() => setSelectedAgent(ag)}
                className={`px-4 py-2 rounded-none text-xs font-mono font-bold uppercase tracking-wider transition-all border ${
                  selectedAgent?.id === ag.id
                    ? 'bg-sky-400/15 border-sky-400 text-sky-400 shadow-[0_0_12px_rgba(56,189,248,0.2)]'
                    : 'bg-zinc-950 border-zinc-900 text-zinc-400 hover:border-zinc-800 hover:text-white'
                }`}
              >
                {ag.name}
              </button>
            ))}
          </div>
        )}

        {loading ? (
          <div className="p-16 text-center rounded-none bg-black border border-zinc-800 text-zinc-400 font-mono text-xs space-y-3">
            <div className="w-6 h-6 border-2 border-sky-400 border-t-transparent rounded-none animate-spin mx-auto" />
            <p>Loading registered Docker agents...</p>
          </div>
        ) : !selectedAgent ? (
          <div className="p-16 text-center rounded-none bg-black border border-zinc-800 space-y-4 shadow-xl">
            <h3 className="text-xl font-bold text-white uppercase tracking-wide">No Agents Registered Yet</h3>
            <p className="text-zinc-400 text-xs max-w-md mx-auto leading-relaxed">
              Register a Docker migration agent to connect your source databases and start profiling schema metadata.
            </p>
            <div className="pt-2">
              <a
                href="/agents/create"
                className="inline-block py-3 px-8 rounded-none bg-sky-400 hover:bg-sky-300 text-black text-xs font-bold uppercase tracking-wider transition-colors"
              >
                Create Migration Agent
              </a>
            </div>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Live Agent Status Banner */}
            <AgentStatusBanner
              agent={selectedAgent}
              onMetadataProfiled={() => {
                // Refresh catalog when WS signals METADATA_PROFILED
                setRefreshKey((prev) => prev + 1);
              }}
            />

            {/* Schema Catalog Viewer */}
            {selectedAgent.data_sources && selectedAgent.data_sources.length > 0 ? (
              <>
                <SchemaCatalogViewer key={refreshKey} dataSources={selectedAgent.data_sources} />

                {/* Generate AI Migration Plan Action */}
                <GeneratePlanAction agentId={selectedAgent.id} />
              </>
            ) : (
              <div className="p-8 rounded-none bg-black border border-zinc-800 text-center font-mono text-xs text-zinc-400">
                No data sources attached to this agent.
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
