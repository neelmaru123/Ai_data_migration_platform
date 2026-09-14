'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import TopologySelector, { TOPOLOGY_OPTIONS } from '../../../components/agents/TopologySelector';
import DatabaseConfigForm from '../../../components/agents/DatabaseConfigForm';
import DockerCommandOutput from '../../../components/agents/DockerCommandOutput';
import {
  AgentDetailResponse,
  AgentDockerCommandResponse,
  InitialDataSourceCreate,
  TopologyType,
} from '../../../types/agent';
import agentService from '../../../services/agentService';
import toast from 'react-hot-toast';
import { ArrowLeft, ChevronRight } from 'lucide-react';

export default function AgentCreatePage() {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [selectedTopology, setSelectedTopology] = useState<TopologyType>('2:1');
  const [customSourceCount, setCustomSourceCount] = useState<number>(4);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Results from Step 2 API submission
  const [createdAgent, setCreatedAgent] = useState<AgentDetailResponse | null>(null);
  const [dockerCmdData, setDockerCmdData] = useState<AgentDockerCommandResponse | null>(null);
  const [submittedSources, setSubmittedSources] = useState<InitialDataSourceCreate[]>([]);
  const [submittedDestination, setSubmittedDestination] = useState<InitialDataSourceCreate | null>(null);
  const [connectionDetailsByIdentifier, setConnectionDetailsByIdentifier] = useState<
    Record<string, { host: string; port: string; username: string; database: string; ssl: boolean }>
  >({});

  // Compute number of source databases needed
  const getSourceCount = (): number => {
    if (selectedTopology === 'custom') return customSourceCount;
    const option = TOPOLOGY_OPTIONS.find((opt) => opt.id === selectedTopology);
    return option ? option.sourceCount : 2;
  };

  // Handle Step 2 API Submission
  const handleFormSubmit = async (formData: {
    agentName: string;
    agentIdentifier: string;
    sources: InitialDataSourceCreate[];
    destination: InitialDataSourceCreate;
    connectionDetailsByIdentifier: Record<string, { host: string; port: string; username: string; database: string; ssl: boolean }>;
  }) => {
    setIsSubmitting(true);
    try {
      // 1. Prepare payload with data sources array
      // NOTE: connectionDetailsByIdentifier is deliberately NOT included in this
      // payload -- it is stored in local component state below and only ever
      // used in the browser to build the displayed docker command. It is never
      // sent to the backend API.
      const allDataSources: InitialDataSourceCreate[] = [
        ...formData.sources.map((src) => ({ ...src, role: 'source' as const })),
        { ...formData.destination, role: 'target' as const },
      ];
      const payload = {
        name: formData.agentName,
        agent_identifier: formData.agentIdentifier,
        data_sources: allDataSources,
      };
      setSubmittedSources(formData.sources);
      setSubmittedDestination(formData.destination);
      setConnectionDetailsByIdentifier(formData.connectionDetailsByIdentifier);
      // 2. Call agent creation API endpoint (returns agent detail + docker_command)
      const agentRes = await agentService.createAgent(payload);
      setCreatedAgent(agentRes);

      // 3. Fetch explicit docker-command payload if missing from agent detail
      if (!agentRes.docker_command) {
        try {
          const cmdRes = await agentService.getAgentDockerCommand(agentRes.id);
          setDockerCmdData(cmdRes);
        } catch {
          // Ignored
        }
      }

      toast.success('Agent registered successfully!');
      setStep(3);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to create agent.';
      toast.error(`Error: ${msg}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setCreatedAgent(null);
    setDockerCmdData(null);
    setStep(1);
  };

  return (
    <div className="min-h-screen bg-black text-slate-100 flex flex-col justify-between selection:bg-sky-400 selection:text-black">
      {/* Top Background Glow - Sky Blue Accent */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-96 bg-gradient-to-b from-sky-400/15 via-sky-500/5 to-transparent blur-3xl pointer-events-none -z-10" />

      {/* Main Container */}
      <main className="container mx-auto px-4 py-8 md:py-12 max-w-6xl space-y-8 font-mono">
        {/* Top Breadcrumb Navigation */}
        <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono">
          <Link href="/dashboard" className="text-sky-400 hover:text-sky-300 flex items-center gap-1 font-bold">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Dashboard</span>
          </Link>
          <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />
          <span className="text-white font-bold">Register New Agent</span>
        </div>

        {/* Wizard Progress Bar */}
        <div className="w-full max-w-3xl mx-auto">
          <div className="flex items-center justify-between relative">
            {/* Connecting Track Line */}
            <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-zinc-800 -translate-y-1/2 -z-10" />
            <div
              className="absolute top-1/2 left-0 h-0.5 bg-gradient-to-r from-sky-400 to-sky-500 -translate-y-1/2 transition-all duration-500 -z-10"
              style={{
                width: step === 1 ? '0%' : step === 2 ? '50%' : '100%',
              }}
            />

            {/* Step 1 Pill */}
            <div
              onClick={() => step > 1 && setStep(1)}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-none text-[11px] font-mono font-bold uppercase tracking-wider transition-all cursor-pointer ${
                step >= 1
                  ? 'bg-black border border-sky-400 text-sky-400 shadow-[0_0_15px_rgba(56,189,248,0.2)]'
                  : 'bg-black border border-zinc-800 text-zinc-500'
              }`}
            >
              <span className="hidden sm:inline">1. Topology</span>
              <span className="sm:hidden">1</span>
            </div>

            {/* Step 2 Pill */}
            <div
              onClick={() => step > 2 && setStep(2)}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-none text-[11px] font-mono font-bold uppercase tracking-wider transition-all cursor-pointer ${
                step >= 2
                  ? 'bg-black border border-sky-400 text-sky-400 shadow-[0_0_15px_rgba(56,189,248,0.2)]'
                  : 'bg-black border border-zinc-800 text-zinc-500'
              }`}
            >
              <span className="hidden sm:inline">2. Databases</span>
              <span className="sm:hidden">2</span>
            </div>

            {/* Step 3 Pill */}
            <div
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-none text-[11px] font-mono font-bold uppercase tracking-wider transition-all ${
                step === 3
                  ? 'bg-black border border-sky-400 text-sky-400 shadow-[0_0_15px_rgba(56,189,248,0.2)]'
                  : 'bg-black border border-zinc-800 text-zinc-500'
              }`}
            >
              <span className="hidden sm:inline">3. Docker CMD</span>
              <span className="sm:hidden">3</span>
            </div>
          </div>
        </div>

        {/* Wizard Step Render */}
        {step === 1 && (
          <TopologySelector
            selectedTopology={selectedTopology}
            customSourceCount={customSourceCount}
            onSelectTopology={(topo) => setSelectedTopology(topo)}
            onCustomSourceCountChange={(count) => setCustomSourceCount(count)}
            onNext={() => setStep(2)}
          />
        )}

        {step === 2 && (
          <DatabaseConfigForm
            sourceCount={getSourceCount()}
            onSubmit={handleFormSubmit}
            onBack={() => setStep(1)}
            isSubmitting={isSubmitting}
          />
        )}

        {step === 3 && createdAgent && (
          <DockerCommandOutput
            agent={createdAgent}
            dockerCmdData={dockerCmdData}
            onReset={handleReset}
            sources={submittedSources}
            destination={submittedDestination}
            connectionDetailsByIdentifier={connectionDetailsByIdentifier}
          />
        )}
      </main>

      {/* Page Footer */}
      <footer className="border-t border-zinc-900 py-6 text-center text-xs font-mono text-zinc-500">
        Migraflow Platform • On-Premise Docker Agent Setup
      </footer>
    </div>
  );
}
