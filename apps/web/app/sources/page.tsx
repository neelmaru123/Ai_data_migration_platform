'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { AgentDetailResponse } from '../../types/agent';
import agentService from '../../services/agentService';
import AgentStatusBanner from '../../components/agents/AgentStatusBanner';
import SchemaCatalogViewer from '../../components/profiling/SchemaCatalogViewer';
import GeneratePlanAction from '../../components/profiling/GeneratePlanAction';
import { ArrowLeft, ChevronRight } from 'lucide-react';

function SourcesPageContent() {
  const searchParams = useSearchParams();
  const agentIdParam = searchParams.get('agentId');

  const [selectedAgent, setSelectedAgent] = useState<AgentDetailResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState<number>(0);

  const fetchSelectedAgent = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const list = await agentService.listAgents();

      if (list && list.length > 0) {
        if (agentIdParam) {
          const matched = list.find((a) => a.id === agentIdParam);
          setSelectedAgent(matched || list[0]);
        } else {
          setSelectedAgent(list[0]);
        }
      } else {
        setSelectedAgent(null);
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to fetch agent details.';
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSelectedAgent();
  }, [agentIdParam]);

  return (
    <div className="min-h-screen bg-black text-slate-100 flex flex-col justify-between selection:bg-sky-400 selection:text-black">
      {/* Background Accent Glow */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-96 bg-gradient-to-b from-sky-400/15 via-sky-500/5 to-transparent blur-3xl pointer-events-none -z-10" />

      {/* Main Container */}
      <main className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 flex-1 font-mono">
        {/* Top Breadcrumb Navigation */}
        <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono">
          <Link href="/dashboard" className="text-sky-400 hover:text-sky-300 flex items-center gap-1 font-bold">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Dashboard</span>
          </Link>
          <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />
          <span>Agents</span>
          <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />
          <span className="text-white font-bold">{selectedAgent?.name || 'Agent Details'}</span>
        </div>

        {/* Header */}
        <div className="border-b border-zinc-800 pb-6 font-sans">
          <div>
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-none text-[11px] font-mono font-bold uppercase tracking-widest bg-sky-400/10 text-sky-400 border border-sky-400/30 mb-2">
              CATALOG PROFILER & SCHEMA INSPECTION
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight sm:text-4xl uppercase">
              {selectedAgent ? `${selectedAgent.name} — Schema Inspection` : 'Data Sources & Schema Inspection'}
            </h1>
            <p className="text-zinc-400 text-xs sm:text-sm max-w-2xl mt-1 leading-relaxed font-mono">
              Inspect database tables, column types, constraints, and relationships profiled by this agent daemon.
            </p>
          </div>
        </div>

        {loading ? (
          <div className="p-16 text-center rounded-none bg-black border border-zinc-800 text-zinc-400 font-mono text-xs space-y-3">
            <div className="w-6 h-6 border-2 border-sky-400 border-t-transparent rounded-none animate-spin mx-auto" />
            <p>Loading agent details and schema snapshot...</p>
          </div>
        ) : errorMsg ? (
          <div className="p-8 text-center rounded-none bg-black border border-rose-500/30 text-rose-400 text-xs">
            {errorMsg}
          </div>
        ) : !selectedAgent ? (
          <div className="p-16 text-center rounded-none bg-black border border-zinc-800 space-y-4 shadow-xl font-mono">
            <h3 className="text-xl font-bold text-white uppercase tracking-wide font-sans">No Agent Found</h3>
            <p className="text-zinc-400 text-xs max-w-md mx-auto leading-relaxed">
              Register a Docker migration agent to connect your source databases and start profiling schema metadata.
            </p>
            <div className="pt-2">
              <Link
                href="/agents/create"
                className="inline-block py-3 px-8 rounded-none bg-sky-400 hover:bg-sky-300 text-black text-xs font-bold uppercase tracking-wider transition-colors"
              >
                Create Migration Agent
              </Link>
            </div>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Live Agent Status Banner */}
            <AgentStatusBanner
              agent={selectedAgent}
              onMetadataProfiled={() => {
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

export default function SourcesPage() {
  return (
    <Suspense fallback={<div className="p-16 text-center text-zinc-400 font-mono text-xs">Loading page...</div>}>
      <SourcesPageContent />
    </Suspense>
  );
}
