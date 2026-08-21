'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { AgentDetailResponse, AgentDockerCommandResponse } from '../../types/agent';
import agentService from '../../services/agentService';
import { Activity, Plus, Terminal, Trash2, ArrowRight, Copy, Check, RefreshCw, ShieldAlert, Monitor, Code, FileCode } from 'lucide-react';
import toast from 'react-hot-toast';

export default function DashboardPage() {
  const [agents, setAgents] = useState<AgentDetailResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Modal State for Docker Commands
  const [selectedAgentForCmd, setSelectedAgentForCmd] = useState<AgentDetailResponse | null>(null);
  const [dockerCmdData, setDockerCmdData] = useState<AgentDockerCommandResponse | null>(null);
  const [loadingCmd, setLoadingCmd] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'powershell' | 'bash' | 'oneline' | 'env'>('powershell');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Modal State for Agent Deletion
  const [agentToDelete, setAgentToDelete] = useState<AgentDetailResponse | null>(null);
  const [deleting, setDeleting] = useState<boolean>(false);

  const fetchAgents = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const list = await agentService.listAgents();
      setAgents(list);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to fetch registered agents.';
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const handleOpenDockerCmdModal = async (ag: AgentDetailResponse) => {
    setSelectedAgentForCmd(ag);
    setDockerCmdData(null);
    setLoadingCmd(true);
    try {
      const cmdRes = await agentService.getAgentDockerCommand(ag.id);
      setDockerCmdData(cmdRes);
    } catch {
      toast.error('Failed to fetch Docker commands for this agent.');
    } finally {
      setLoadingCmd(false);
    }
  };

  const totalAgents = agents.length;
  const onlineAgents = agents.filter((ag) => (ag.status || '').toLowerCase() === 'online').length;
  const degradedAgents = agents.filter((ag) => (ag.status || '').toLowerCase() === 'degraded').length;
  const totalDataSources = agents.reduce((acc, ag) => acc + (ag.data_sources?.length || 0), 0);

  const handleCopyText = (text: string, key: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    toast.success('Copied to clipboard!');
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const handleDeleteAgent = async () => {
    if (!agentToDelete) return;
    try {
      setDeleting(true);
      await agentService.deleteAgent(agentToDelete.id);
      toast.success(`Agent '${agentToDelete.name}' deleted successfully.`);
      setAgentToDelete(null);
      fetchAgents();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to delete agent.');
    } finally {
      setDeleting(false);
    }
  };

  const getDisplayedCommand = (): string => {
    if (!dockerCmdData) return '';
    switch (activeTab) {
      case 'powershell':
        return dockerCmdData.docker_command_powershell || dockerCmdData.docker_command;
      case 'bash':
        return dockerCmdData.docker_command;
      case 'oneline':
        return dockerCmdData.docker_command_oneline || dockerCmdData.docker_command;
      case 'env':
        return dockerCmdData.env_template;
      default:
        return dockerCmdData.docker_command_powershell || dockerCmdData.docker_command;
    }
  };

  return (
    <div className="min-h-screen bg-black text-slate-100 flex flex-col justify-between selection:bg-sky-400 selection:text-black font-sans">
      {/* Background Ambient Glow */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-96 bg-gradient-to-b from-sky-400/15 via-sky-500/5 to-transparent blur-3xl pointer-events-none -z-10" />

      <main className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 flex-1">
        {/* Top Header & Actions */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-zinc-800 pb-6">
          <div>
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-none text-[11px] font-mono font-bold uppercase tracking-widest bg-sky-400/10 text-sky-400 border border-sky-400/30 mb-2">
              <Activity className="w-3.5 h-3.5" />
              MIGRATION CONTROL PLANE
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight sm:text-4xl uppercase font-sans">
              Agent Migration Dashboard
            </h1>
            <p className="text-zinc-400 text-xs sm:text-sm max-w-2xl mt-1 leading-relaxed font-mono">
              Manage your registered Docker migration agents, inspect connection status, and trigger AI schema migration blueprints.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={fetchAgents}
              className="py-3 px-4 rounded-none bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white text-xs font-mono font-bold uppercase tracking-wider border border-zinc-800 transition-colors flex items-center gap-2"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh
            </button>

            <Link
              href="/agents/create"
              className="py-3 px-6 rounded-none bg-sky-400 hover:bg-sky-300 text-black text-xs font-bold uppercase tracking-wider transition-colors shadow-lg shadow-sky-950/50 flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Register New Agent
            </Link>
          </div>
        </div>

        {/* Global Agent Metrics Overview */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 font-mono">
          <div className="p-4 rounded-none bg-black border border-zinc-800 space-y-1 shadow-xl">
            <span className="text-[10px] font-bold text-zinc-500 uppercase block">TOTAL REGISTERED AGENTS</span>
            <span className="text-2xl font-extrabold text-white">{totalAgents}</span>
            <span className="text-[10px] text-zinc-400 block">Configured daemons</span>
          </div>

          <div className="p-4 rounded-none bg-black border border-zinc-800 space-y-1 shadow-xl">
            <span className="text-[10px] font-bold text-zinc-500 uppercase block">ONLINE AGENTS</span>
            <span className="text-2xl font-extrabold text-sky-400 flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-none bg-sky-400 inline-block animate-pulse" />
              {onlineAgents}
            </span>
            <span className="text-[10px] text-sky-400/80 block">Active heartbeats</span>
          </div>

          <div className="p-4 rounded-none bg-black border border-zinc-800 space-y-1 shadow-xl">
            <span className="text-[10px] font-bold text-zinc-500 uppercase block font-mono">DEGRADED / WARNING</span>
            <span className={`text-2xl font-extrabold ${degradedAgents > 0 ? 'text-amber-400' : 'text-zinc-500'}`}>
              {degradedAgents}
            </span>
            <span className="text-[10px] text-zinc-400 block font-mono">Connection warnings</span>
          </div>

          <div className="p-4 rounded-none bg-black border border-zinc-800 space-y-1 shadow-xl">
            <span className="text-[10px] font-bold text-zinc-500 uppercase block">TOTAL LINKED DATABASES</span>
            <span className="text-2xl font-extrabold text-white">{totalDataSources}</span>
            <span className="text-[10px] text-zinc-400 block">Sources & Target DBs</span>
          </div>
        </div>

        {/* Agent Cards Grid Section */}
        <div className="space-y-4 font-mono">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <span className="w-2 h-2 rounded-none bg-sky-400 inline-block" />
              Your Registered Migration Agents ({agents.length})
            </h2>
          </div>

          {loading ? (
            <div className="p-16 text-center rounded-none bg-black border border-zinc-800 text-zinc-400 text-xs space-y-3">
              <div className="w-6 h-6 border-2 border-sky-400 border-t-transparent rounded-none animate-spin mx-auto" />
              <p>Loading agent configuration registry...</p>
            </div>
          ) : errorMsg ? (
            <div className="p-8 text-center rounded-none bg-black border border-rose-500/30 text-rose-400 text-xs">
              {errorMsg}
            </div>
          ) : agents.length === 0 ? (
            <div className="p-16 text-center rounded-none bg-black border border-zinc-800 space-y-4 shadow-xl">
              <div className="w-12 h-12 rounded-none bg-sky-400/10 border border-sky-400/30 text-sky-400 flex items-center justify-center mx-auto text-xl font-bold">
                ⚡
              </div>
              <h3 className="text-xl font-bold text-white uppercase tracking-wide">No Agents Registered Yet</h3>
              <p className="text-zinc-400 text-xs max-w-md mx-auto leading-relaxed">
                Register a Docker migration agent to connect your source databases and start profiling schemas.
              </p>
              <div className="pt-2">
                <Link
                  href="/agents/create"
                  className="inline-flex items-center gap-2 py-3 px-8 rounded-none bg-sky-400 hover:bg-sky-300 text-black text-xs font-bold uppercase tracking-wider transition-colors shadow-lg shadow-sky-950/50"
                >
                  <Plus className="w-4 h-4" />
                  Create Migration Agent
                </Link>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {agents.map((ag) => {
                const stLower = (ag.status || 'offline').toLowerCase();
                const isOnline = stLower === 'online';
                const isDegraded = stLower === 'degraded';

                return (
                  <div
                    key={ag.id}
                    className="p-6 rounded-none bg-black border border-zinc-800 hover:border-sky-400/50 transition-all space-y-5 flex flex-col justify-between shadow-xl group"
                  >
                    <div className="space-y-4">
                      {/* Agent Card Header */}
                      <div className="flex items-start justify-between gap-3 border-b border-zinc-900 pb-3">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span
                              className={`w-2.5 h-2.5 rounded-none ${
                                isOnline
                                  ? 'bg-sky-400 shadow-[0_0_10px_#38bdf8] animate-pulse'
                                  : isDegraded
                                  ? 'bg-amber-400 shadow-[0_0_10px_#f59e0b] animate-pulse'
                                  : 'bg-zinc-600'
                              }`}
                            />
                            <span
                              className={`text-[9px] font-bold tracking-widest px-2 py-0.5 uppercase border ${
                                isOnline
                                  ? 'bg-sky-400/15 text-sky-400 border-sky-400/30'
                                  : isDegraded
                                  ? 'bg-amber-400/15 text-amber-400 border-amber-400/30'
                                  : 'bg-zinc-800 text-zinc-400 border-zinc-700'
                              }`}
                            >
                              {stLower.toUpperCase()}
                            </span>
                          </div>
                          <h3 className="text-lg font-extrabold text-white uppercase font-sans tracking-wide group-hover:text-sky-400 transition-colors">
                            {ag.name}
                          </h3>
                        </div>

                        <button
                          type="button"
                          onClick={() => setAgentToDelete(ag)}
                          className="p-1.5 text-zinc-600 hover:text-rose-400 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/30 transition-colors"
                          title="Delete Agent"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>

                      {/* Identifier & Version Badges */}
                      <div className="flex items-center justify-between text-xs font-mono text-zinc-400">
                        <span>
                          ID: <span className="text-sky-400 font-bold">{ag.agent_identifier}</span>
                        </span>
                        <span className="text-[10px] text-zinc-500">
                          v{ag.version || '1.0.0'}
                        </span>
                      </div>

                      {/* Connected Data Sources List */}
                      <div className="space-y-2 pt-1 border-t border-zinc-900">
                        <div className="text-[10px] text-zinc-500 font-bold uppercase flex items-center justify-between">
                          <span>Connected Databases ({ag.data_sources?.length || 0})</span>
                        </div>

                        <div className="space-y-1.5 max-h-32 overflow-y-auto pr-1">
                          {ag.data_sources && ag.data_sources.length > 0 ? (
                            ag.data_sources.map((ds) => (
                              <div
                                key={ds.id}
                                className="p-2 bg-zinc-950 border border-zinc-900 flex items-center justify-between text-xs"
                              >
                                <span className="text-white font-bold truncate max-w-[140px]">{ds.name}</span>
                                <div className="flex items-center gap-1.5">
                                  <span
                                    className={`px-1.5 py-0.2 text-[9px] font-bold uppercase rounded-none border ${
                                      ds.role === 'target'
                                        ? 'bg-blue-500/10 text-blue-400 border-blue-500/30'
                                        : 'bg-sky-400/10 text-sky-400 border-sky-400/30'
                                    }`}
                                  >
                                    {ds.role.toUpperCase()}
                                  </span>
                                  <span className="text-[9px] text-zinc-400 uppercase font-mono">
                                    {ds.type}
                                  </span>
                                </div>
                              </div>
                            ))
                          ) : (
                            <span className="text-zinc-600 text-xs italic block">No database identities attached.</span>
                          )}
                        </div>
                      </div>

                      {/* Ping Info */}
                      <div className="text-[10px] text-zinc-500 font-mono pt-1">
                        Last Ping:{' '}
                        {ag.last_seen_at ? (
                          <span className="text-zinc-300">{new Date(ag.last_seen_at).toLocaleString()}</span>
                        ) : (
                          <span className="text-zinc-600 italic">Never connected</span>
                        )}
                      </div>
                    </div>

                    {/* Action Footer Buttons */}
                    <div className="pt-4 border-t border-zinc-900 space-y-2">
                      <Link
                        href={`/sources?agentId=${ag.id}`}
                        className="w-full py-2.5 px-4 rounded-none bg-sky-400 hover:bg-sky-300 text-black text-xs font-bold uppercase tracking-wider transition-colors flex items-center justify-center gap-2 shadow-md shadow-sky-950/50"
                      >
                        <span>Inspect Schemas & Migration Plan</span>
                        <ArrowRight className="w-4 h-4" />
                      </Link>

                      <button
                        type="button"
                        onClick={() => handleOpenDockerCmdModal(ag)}
                        className="w-full py-2 px-4 rounded-none bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white text-[11px] font-mono font-bold uppercase tracking-wider border border-zinc-800 transition-colors flex items-center justify-center gap-2"
                      >
                        <Terminal className="w-3.5 h-3.5 text-sky-400" />
                        <span>View Docker Setup Command</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>

      {/* Docker Command Modal */}
      {selectedAgentForCmd && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-black border border-sky-400/40 p-6 sm:p-8 space-y-6 shadow-[0_0_30px_rgba(56,189,248,0.2)] font-mono animate-fadeIn">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
              <div>
                <span className="text-[10px] font-bold tracking-widest px-2.5 py-0.5 uppercase bg-sky-400/10 text-sky-400 border border-sky-400/30">
                  DOCKER DAEMON SETUP
                </span>
                <h3 className="text-xl font-extrabold text-white uppercase font-sans tracking-wide mt-1">
                  {selectedAgentForCmd.name}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedAgentForCmd(null)}
                className="text-zinc-500 hover:text-white text-xs uppercase font-bold"
              >
                ✕ Close
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <p className="text-zinc-300 leading-relaxed">
                Run this command on your host server to boot the Docker migration agent daemon.
              </p>

              {/* Format Tabs (PowerShell, Bash, Single Line, .env) */}
              <div className="flex items-center gap-1.5 flex-wrap border-b border-zinc-900 pb-2">
                <button
                  type="button"
                  onClick={() => setActiveTab('powershell')}
                  className={`inline-flex items-center gap-1.5 px-3 py-1 text-[11px] font-mono font-semibold uppercase ${
                    activeTab === 'powershell'
                      ? 'bg-sky-400/20 text-sky-400 border border-sky-400/30'
                      : 'text-zinc-400 hover:text-white'
                  }`}
                >
                  <Monitor className="w-3.5 h-3.5" /> PowerShell
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab('bash')}
                  className={`inline-flex items-center gap-1.5 px-3 py-1 text-[11px] font-mono font-semibold uppercase ${
                    activeTab === 'bash'
                      ? 'bg-sky-400/20 text-sky-400 border border-sky-400/30'
                      : 'text-zinc-400 hover:text-white'
                  }`}
                >
                  <Terminal className="w-3.5 h-3.5" /> Bash / Linux
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab('oneline')}
                  className={`inline-flex items-center gap-1.5 px-3 py-1 text-[11px] font-mono font-semibold uppercase ${
                    activeTab === 'oneline'
                      ? 'bg-sky-400/20 text-sky-400 border border-sky-400/30'
                      : 'text-zinc-400 hover:text-white'
                  }`}
                >
                  <Code className="w-3.5 h-3.5" /> Single Line
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab('env')}
                  className={`inline-flex items-center gap-1.5 px-3 py-1 text-[11px] font-mono font-semibold uppercase ${
                    activeTab === 'env'
                      ? 'bg-sky-400/20 text-sky-400 border border-sky-400/30'
                      : 'text-zinc-400 hover:text-white'
                  }`}
                >
                  <FileCode className="w-3.5 h-3.5" /> .env File
                </button>
              </div>

              {/* Command Box */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-[10px] font-bold text-zinc-400 uppercase">
                  <span>{activeTab.toUpperCase()} COMMAND LINE:</span>
                  <button
                    type="button"
                    onClick={() => handleCopyText(getDisplayedCommand(), 'cmd_modal')}
                    className="text-sky-400 hover:text-sky-300 flex items-center gap-1"
                  >
                    {copiedKey === 'cmd_modal' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copiedKey === 'cmd_modal' ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>

                {loadingCmd ? (
                  <div className="p-8 text-center bg-zinc-950 border border-zinc-900 text-sky-400 text-xs flex items-center justify-center gap-2 font-mono">
                    <div className="w-4 h-4 border-2 border-sky-400 border-t-transparent animate-spin" />
                    <span>Fetching Docker CLI setup commands...</span>
                  </div>
                ) : (
                  <pre className="p-4 bg-zinc-950 border border-zinc-900 text-sky-300 overflow-x-auto whitespace-pre-wrap text-[11px] font-mono max-h-60">
                    {getDisplayedCommand() || 'No command available.'}
                  </pre>
                )}
              </div>

              <div className="p-3 bg-sky-400/10 border border-sky-400/30 text-sky-300 text-[11px] leading-relaxed">
                💡 Replace credential placeholders (e.g. <code className="text-white font-bold">&lt;password&gt;</code>) with actual database passwords before executing.
              </div>
            </div>

            <div className="flex justify-end border-t border-zinc-800 pt-4">
              <button
                type="button"
                onClick={() => setSelectedAgentForCmd(null)}
                className="py-2.5 px-6 rounded-none bg-sky-400 text-black font-bold uppercase text-xs hover:bg-sky-300"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Agent Modal */}
      {agentToDelete && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-black border border-rose-500/40 p-6 space-y-6 shadow-[0_0_30px_rgba(244,63,94,0.2)] font-mono animate-fadeIn">
            <div className="flex items-center gap-3 text-rose-400 border-b border-zinc-800 pb-3 font-sans font-extrabold uppercase">
              <ShieldAlert className="w-5 h-5" />
              <span>Confirm Agent Deletion</span>
            </div>

            <p className="text-xs text-zinc-300 leading-relaxed font-mono">
              Are you sure you want to delete agent <strong className="text-white">{agentToDelete.name}</strong> ({agentToDelete.agent_identifier})? This will un-link all attached database identities.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                disabled={deleting}
                onClick={() => setAgentToDelete(null)}
                className="py-2 px-5 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 text-xs font-mono font-bold uppercase border border-zinc-800"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deleting}
                onClick={handleDeleteAgent}
                className="py-2 px-5 bg-rose-500 hover:bg-rose-400 text-white text-xs font-mono font-bold uppercase transition-colors"
              >
                {deleting ? 'Deleting...' : 'Delete Agent'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
