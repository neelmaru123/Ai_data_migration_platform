'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { AgentDetailResponse, AgentDockerCommandResponse } from '../../types/agent';
import agentService from '../../services/agentService';
import { Activity, Plus, Terminal, Trash2, ArrowRight, Copy, Check, RefreshCw, ShieldAlert, ShieldCheck, Monitor, Code, FileCode, AlertTriangle, Sliders, Database, ChevronDown, ChevronUp } from 'lucide-react';
import { ConnectionDetails, substituteConnectionPlaceholders } from '../../lib/dockerCommandUtils';
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
  // Connection details re-entered by the user for THIS viewing session only
  // (never persisted, never sent anywhere -- mirrors the create-agent flow).
  const [modalConnectionDetails, setModalConnectionDetails] = useState<Record<string, ConnectionDetails>>({});
  const [showRegenerateConfirm, setShowRegenerateConfirm] = useState<boolean>(false);
  const [regenerating, setRegenerating] = useState<boolean>(false);
  const [showConnectionConfig, setShowConnectionConfig] = useState<boolean>(false);

  // Modal State for Agent Deletion
  const [agentToDelete, setAgentToDelete] = useState<AgentDetailResponse | null>(null);
  const [deleting, setDeleting] = useState<boolean>(false);

  const fetchAgents = async (isInitial = true) => {
    try {
      if (isInitial) setLoading(true);
      setErrorMsg(null);
      const list = await agentService.listAgents();
      setAgents(list);
    } catch (err: any) {
      if (isInitial) {
        const msg = err.response?.data?.detail || err.message || 'Failed to fetch registered agents.';
        setErrorMsg(msg);
      }
    } finally {
      if (isInitial) setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents(true);
    const interval = setInterval(() => {
      fetchAgents(false);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleOpenDockerCmdModal = async (ag: AgentDetailResponse) => {
    setSelectedAgentForCmd(ag);
    setDockerCmdData(null);
    setModalConnectionDetails({});
    setShowRegenerateConfirm(false);
    setShowConnectionConfig(false);
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

  const handleModalConnectionChange = (
    identifier: string,
    field: keyof ConnectionDetails,
    value: string | boolean
  ) => {
    setModalConnectionDetails((prev) => ({
      ...prev,
      [identifier]: { ...(prev[identifier] || { host: '', port: '', username: '', database: '', ssl: false }), [field]: value },
    }));
  };

  const handleRegenerateToken = async () => {
    if (!selectedAgentForCmd) return;
    setRegenerating(true);
    try {
      const updated = await agentService.regenerateAgentToken(selectedAgentForCmd.id);
      setSelectedAgentForCmd(updated);
      setDockerCmdData({
        agent_id: updated.id,
        agent_identifier: updated.agent_identifier,
        docker_command: updated.docker_command!,
        docker_command_powershell: updated.docker_command_powershell!,
        docker_command_oneline: updated.docker_command_oneline!,
        env_template: updated.env_template!,
        environment_variables: {},
      });
      setShowRegenerateConfirm(false);
      toast.success('Token regenerated. The previous token no longer works -- redeploy your container with the new command below.');
    } catch {
      toast.error('Failed to regenerate token.');
    } finally {
      setRegenerating(false);
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
    if (!dockerCmdData || !selectedAgentForCmd) return '';
    let raw: string;
    switch (activeTab) {
      case 'powershell':
        raw = dockerCmdData.docker_command_powershell || dockerCmdData.docker_command;
        break;
      case 'bash':
        raw = dockerCmdData.docker_command;
        break;
      case 'oneline':
        raw = dockerCmdData.docker_command_oneline || dockerCmdData.docker_command;
        break;
      case 'env':
        raw = dockerCmdData.env_template;
        break;
      default:
        raw = dockerCmdData.docker_command_powershell || dockerCmdData.docker_command;
    }
    const srcList = (selectedAgentForCmd.data_sources || []).filter((d: any) => d.role === 'source');
    const destEntry = (selectedAgentForCmd.data_sources || []).find((d: any) => d.role === 'target' || d.role === 'destination' || d.role === 'dest');
    return substituteConnectionPlaceholders(raw, srcList, destEntry, modalConnectionDetails);
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
              onClick={() => fetchAgents()}
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

              {/* Architecture & Privacy Explainer */}
              <div className="max-w-xl mx-auto my-3 p-4 rounded-none bg-sky-950/20 border border-sky-500/30 text-left flex items-start gap-3">
                <ShieldCheck className="w-5 h-5 text-sky-400 shrink-0 mt-0.5" />
                <p className="text-zinc-300 text-xs leading-relaxed font-mono">
                  Your data never leaves your infrastructure. Migraflow uses a local
                  Docker Agent to inspect and migrate your databases directly on your
                  machine or server -- the cloud application only ever receives schema
                  metadata and migration decisions, never your data or credentials.
                </p>
              </div>

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
                const isError = stLower === 'error';
                const hasFatalError = Boolean(ag.last_error && (isError || stLower === 'offline'));

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
                                  : isError || hasFatalError
                                  ? 'bg-rose-500 shadow-[0_0_10px_#f43f5e] animate-pulse'
                                  : 'bg-zinc-600'
                              }`}
                            />
                            <span
                              className={`text-[9px] font-bold tracking-widest px-2 py-0.5 uppercase border ${
                                isOnline
                                  ? 'bg-sky-400/15 text-sky-400 border-sky-400/30'
                                  : isDegraded
                                  ? 'bg-amber-400/15 text-amber-400 border-amber-400/30'
                                  : isError || hasFatalError
                                  ? 'bg-rose-500/20 text-rose-400 border-rose-500/40 animate-pulse'
                                  : 'bg-zinc-800 text-zinc-400 border-zinc-700'
                              }`}
                            >
                              {(isError || hasFatalError ? 'ERROR' : stLower).toUpperCase()}
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

                      {/* Fatal Stopping Error Notice Box */}
                      {hasFatalError && (
                        <div className="p-3 bg-rose-950/40 border border-rose-500/40 text-xs font-mono space-y-1">
                          <div className="flex items-center justify-between text-[10px] font-bold text-rose-400 uppercase">
                            <span>🚨 Fatal Stopping Error</span>
                            {ag.error_category && (
                              <span className="px-1.5 py-0.2 bg-rose-500/20 border border-rose-500/30 text-[9px]">
                                {ag.error_category.replace(/_/g, ' ')}
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-rose-300/90 line-clamp-3" title={ag.last_error || ''}>
                            {ag.last_error}
                          </p>
                          {ag.last_error_at && (
                            <span className="text-[9px] text-zinc-500 block">
                              Reported: {new Date(ag.last_error_at).toLocaleTimeString()}
                            </span>
                          )}
                        </div>
                      )}

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
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 sm:p-5 animate-fadeIn">
          <div className="w-full max-w-4xl max-h-[90vh] flex flex-col bg-zinc-950 border border-sky-400/40 shadow-[0_0_50px_rgba(56,189,248,0.15)] font-mono overflow-hidden">
            {/* Modal Header - Fixed */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800/80 bg-zinc-900/60 shrink-0">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-sky-400/10 border border-sky-400/30 text-sky-400">
                  <Terminal className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold tracking-widest px-2 py-0.5 uppercase bg-sky-400/10 text-sky-400 border border-sky-400/30">
                      DOCKER DAEMON SETUP
                    </span>
                    <span className="text-[10px] text-zinc-500 font-mono">
                      {selectedAgentForCmd.agent_identifier}
                    </span>
                  </div>
                  <h3 className="text-lg sm:text-xl font-extrabold text-white uppercase font-sans tracking-wide mt-0.5">
                    {selectedAgentForCmd.name}
                  </h3>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedAgentForCmd(null)}
                className="w-8 h-8 flex items-center justify-center text-zinc-400 hover:text-white bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 transition-colors text-sm font-bold"
                aria-label="Close modal"
              >
                ✕
              </button>
            </div>

            {/* Modal Body - Scrollable */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4 text-xs">
              {/* Header explanation & Tabs */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1">
                <p className="text-zinc-400 text-xs">
                  Run this command on your host server to launch the Docker migration agent daemon.
                </p>

                {/* Format Tabs (PowerShell, Bash, Single Line, .env) */}
                <div className="flex items-center gap-1 flex-wrap bg-black/60 p-1 border border-zinc-900 shrink-0">
                  <button
                    type="button"
                    onClick={() => setActiveTab('powershell')}
                    className={`inline-flex items-center gap-1.5 px-3 py-1 text-[11px] font-mono font-semibold uppercase transition-colors ${
                      activeTab === 'powershell'
                        ? 'bg-sky-400/20 text-sky-400 border border-sky-400/40 shadow-sm'
                        : 'text-zinc-400 hover:text-white border border-transparent'
                    }`}
                  >
                    <Monitor className="w-3.5 h-3.5" /> PowerShell
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveTab('bash')}
                    className={`inline-flex items-center gap-1.5 px-3 py-1 text-[11px] font-mono font-semibold uppercase transition-colors ${
                      activeTab === 'bash'
                        ? 'bg-sky-400/20 text-sky-400 border border-sky-400/40 shadow-sm'
                        : 'text-zinc-400 hover:text-white border border-transparent'
                    }`}
                  >
                    <Terminal className="w-3.5 h-3.5" /> Bash / Linux
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveTab('oneline')}
                    className={`inline-flex items-center gap-1.5 px-3 py-1 text-[11px] font-mono font-semibold uppercase transition-colors ${
                      activeTab === 'oneline'
                        ? 'bg-sky-400/20 text-sky-400 border border-sky-400/40 shadow-sm'
                        : 'text-zinc-400 hover:text-white border border-transparent'
                    }`}
                  >
                    <Code className="w-3.5 h-3.5" /> Single Line
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveTab('env')}
                    className={`inline-flex items-center gap-1.5 px-3 py-1 text-[11px] font-mono font-semibold uppercase transition-colors ${
                      activeTab === 'env'
                        ? 'bg-sky-400/20 text-sky-400 border border-sky-400/40 shadow-sm'
                        : 'text-zinc-400 hover:text-white border border-transparent'
                    }`}
                  >
                    <FileCode className="w-3.5 h-3.5" /> .env File
                  </button>
                </div>
              </div>

              {/* Command Display Terminal */}
              <div className="border border-zinc-800 bg-black shadow-inner overflow-hidden">
                <div className="flex items-center justify-between px-3.5 py-1.5 bg-zinc-900/70 border-b border-zinc-800/80 text-[10px] font-bold">
                  <div className="flex items-center gap-2 text-zinc-400">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80 inline-block animate-pulse" />
                    <span className="uppercase font-mono tracking-wider text-sky-400">
                      {activeTab.toUpperCase()} SCRIPT PREVIEW
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleCopyText(getDisplayedCommand(), 'cmd_modal')}
                    className="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-sky-400/10 hover:bg-sky-400/20 text-sky-400 border border-sky-400/30 hover:border-sky-400/50 transition-colors uppercase font-mono text-[10px] font-bold"
                  >
                    {copiedKey === 'cmd_modal' ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-400" />
                        <span className="text-emerald-400">Copied to clipboard</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        <span>Copy Script</span>
                      </>
                    )}
                  </button>
                </div>

                {loadingCmd ? (
                  <div className="p-8 text-center bg-black text-sky-400 text-xs flex items-center justify-center gap-2 font-mono">
                    <div className="w-4 h-4 border-2 border-sky-400 border-t-transparent animate-spin" />
                    <span>Fetching Docker CLI setup commands...</span>
                  </div>
                ) : (
                  <pre className="p-4 bg-black text-sky-300 overflow-x-auto whitespace-pre-wrap text-[11px] font-mono max-h-48 leading-relaxed selection:bg-sky-400 selection:text-black">
                    {getDisplayedCommand() || 'No command available.'}
                  </pre>
                )}
              </div>

              {/* Collapsible Connection Detail Re-entry */}
              {selectedAgentForCmd.data_sources && selectedAgentForCmd.data_sources.length > 0 && (
                <div className="border border-zinc-800/90 bg-zinc-950/60 transition-all">
                  <button
                    type="button"
                    onClick={() => setShowConnectionConfig(!showConnectionConfig)}
                    className="w-full flex items-center justify-between p-3 text-left hover:bg-zinc-900/40 transition-colors"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <Sliders className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                      <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-200">
                        Auto-Fill Connection Parameters
                      </span>
                      <span className="text-[10px] text-zinc-500 font-normal hidden sm:inline">
                        — Host, port, username & db are substituted in browser memory
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 text-zinc-400 text-[10px] font-semibold uppercase">
                      <span>{showConnectionConfig ? 'Collapse' : 'Expand'}</span>
                      {showConnectionConfig ? (
                        <ChevronUp className="w-3.5 h-3.5 text-sky-400" />
                      ) : (
                        <ChevronDown className="w-3.5 h-3.5 text-sky-400" />
                      )}
                    </div>
                  </button>

                  {showConnectionConfig && (
                    <div className="p-3.5 pt-1 border-t border-zinc-900 space-y-3">
                      <p className="text-[10px] text-zinc-400 leading-relaxed">
                        These parameters were never stored on the server. Type them here to dynamically replace &lt;..._HOST&gt;, &lt;..._PORT&gt;, etc. in the command preview above:
                      </p>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {selectedAgentForCmd.data_sources.map((ds: any) => {
                          const isSource = ds.role === 'source';
                          return (
                            <div
                              key={ds.identifier}
                              className={`p-3 border bg-black/90 space-y-2 ${
                                isSource ? 'border-sky-500/20' : 'border-emerald-500/20'
                              }`}
                            >
                              <div className="flex items-center justify-between pb-1 border-b border-zinc-900">
                                <div className="flex items-center gap-1.5 min-w-0">
                                  <Database
                                    className={`w-3.5 h-3.5 shrink-0 ${
                                      isSource ? 'text-sky-400' : 'text-emerald-400'
                                    }`}
                                  />
                                  <span className="text-white text-[11px] font-bold truncate">
                                    {ds.identifier}
                                  </span>
                                </div>
                                <span
                                  className={`text-[9px] font-bold px-1.5 py-0.2 uppercase border ${
                                    isSource
                                      ? 'bg-sky-400/10 text-sky-400 border-sky-400/30'
                                      : 'bg-emerald-400/10 text-emerald-400 border-emerald-400/30'
                                  }`}
                                >
                                  {ds.role}
                                </span>
                              </div>

                              <div className="grid grid-cols-3 gap-1.5">
                                <input
                                  type="text"
                                  value={modalConnectionDetails[ds.identifier]?.host || ''}
                                  onChange={(e) =>
                                    handleModalConnectionChange(ds.identifier, 'host', e.target.value)
                                  }
                                  placeholder="Host (e.g. localhost)"
                                  className="col-span-2 px-2.5 py-1.5 bg-zinc-950 border border-zinc-800 text-white text-[11px] font-mono focus:border-sky-400 focus:outline-none transition-colors"
                                />
                                <input
                                  type="text"
                                  value={modalConnectionDetails[ds.identifier]?.port || ''}
                                  onChange={(e) =>
                                    handleModalConnectionChange(ds.identifier, 'port', e.target.value)
                                  }
                                  placeholder="Port"
                                  className="px-2.5 py-1.5 bg-zinc-950 border border-zinc-800 text-white text-[11px] font-mono focus:border-sky-400 focus:outline-none transition-colors"
                                />
                              </div>

                              <div className="grid grid-cols-2 gap-1.5">
                                <input
                                  type="text"
                                  value={modalConnectionDetails[ds.identifier]?.username || ''}
                                  onChange={(e) =>
                                    handleModalConnectionChange(ds.identifier, 'username', e.target.value)
                                  }
                                  placeholder="Username"
                                  className="px-2.5 py-1.5 bg-zinc-950 border border-zinc-800 text-white text-[11px] font-mono focus:border-sky-400 focus:outline-none transition-colors"
                                />
                                <input
                                  type="text"
                                  value={modalConnectionDetails[ds.identifier]?.database || ''}
                                  onChange={(e) =>
                                    handleModalConnectionChange(ds.identifier, 'database', e.target.value)
                                  }
                                  placeholder="Database Name"
                                  className="px-2.5 py-1.5 bg-zinc-950 border border-zinc-800 text-white text-[11px] font-mono focus:border-sky-400 focus:outline-none transition-colors"
                                />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Password Notice */}
              <div className="p-3 bg-sky-400/5 border border-sky-400/25 text-sky-300 text-[11px] leading-relaxed flex items-center gap-2">
                <span className="text-base shrink-0">💡</span>
                <span>
                  Replace password placeholders (e.g. <code className="text-white font-bold">&lt;..._PASSWORD&gt;</code>) with actual database passwords before executing. Passwords are never stored on the server.
                </span>
              </div>

              {/* Regenerate Token Section */}
              <div className="p-3 bg-amber-500/5 border border-amber-500/30">
                {!showRegenerateConfirm ? (
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                      <span className="text-zinc-300 text-[11px]">
                        Need a new token or redeploying your Docker daemon?
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowRegenerateConfirm(true)}
                      className="py-1.5 px-3 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 hover:text-amber-300 border border-amber-500/40 text-[10px] font-bold uppercase tracking-wider transition-colors shrink-0 flex items-center justify-center gap-1.5"
                    >
                      <span>⚠ Regenerate Agent Token</span>
                    </button>
                  </div>
                ) : (
                  <div className="space-y-3 p-3 bg-black/80 border border-amber-500/40">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                      <p className="text-[11px] text-amber-300 leading-relaxed">
                        <strong className="text-white">Security Warning:</strong> This will immediately invalidate the current token. Any currently running Docker container using the old token will fail authentication and must be redeployed with the new command above.
                      </p>
                    </div>
                    <div className="flex items-center gap-2 pt-1">
                      <button
                        type="button"
                        onClick={handleRegenerateToken}
                        disabled={regenerating}
                        className="py-1.5 px-4 bg-amber-500 text-black font-bold uppercase text-[11px] hover:bg-amber-400 disabled:opacity-50 transition-colors flex items-center gap-2"
                      >
                        {regenerating && (
                          <div className="w-3.5 h-3.5 border-2 border-black border-t-transparent animate-spin" />
                        )}
                        <span>{regenerating ? 'Regenerating...' : 'Confirm Regenerate'}</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowRegenerateConfirm(false)}
                        className="py-1.5 px-4 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white font-bold uppercase text-[11px] border border-zinc-800 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Modal Footer - Fixed */}
            <div className="flex items-center justify-between px-6 py-3.5 border-t border-zinc-800/80 bg-zinc-900/60 shrink-0">
              <span className="text-[10px] text-zinc-500 font-mono hidden sm:inline">
                Credentials & tokens configured strictly in memory
              </span>
              <button
                type="button"
                onClick={() => setSelectedAgentForCmd(null)}
                className="py-2 px-6 bg-sky-400 text-black font-bold uppercase text-xs hover:bg-sky-300 transition-colors shadow-md shadow-sky-950/50 ml-auto"
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
