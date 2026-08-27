'use client';

import React, { useState, useEffect } from 'react';
import { AgentDetailResponse, DataSourceResponse } from '../../types/agent';
import agentService from '../../services/agentService';

interface AgentStatusBannerProps {
  agent: AgentDetailResponse;
  onStatusChange?: (newStatus: string) => void;
  onMetadataProfiled?: () => void;
}

export const AgentStatusBanner: React.FC<AgentStatusBannerProps> = ({
  agent,
  onStatusChange,
  onMetadataProfiled,
}) => {
  const [status, setStatus] = useState<string>(agent.status || 'offline');
  const [lastSeen, setLastSeen] = useState<string | null>(agent.last_seen_at || null);
  const [dataSources, setDataSources] = useState<DataSourceResponse[]>(agent.data_sources || []);

  const stLower = status.toLowerCase();
  const isOnline = stLower === 'online';
  const isDegraded = stLower === 'degraded';
  const isOffline = stLower === 'offline';

  useEffect(() => {
    setStatus(agent.status || 'offline');
    setLastSeen(agent.last_seen_at || null);
    setDataSources(agent.data_sources || []);
  }, [agent.status, agent.last_seen_at, agent.data_sources]);

  // Subscribe to real-time WebSocket for live heartbeat ping & METADATA_PROFILED events
  useEffect(() => {
    const token = agent.api_token || (typeof window !== 'undefined' ? localStorage.getItem('access_token') : null);
    if (!agent.id) return;

    let ws: WebSocket | null = null;
    try {
      if (token) {
        ws = agentService.connectAgentWebSocket(
          agent.id,
          token,
          (eventData) => {
            if (eventData.status) {
              setStatus(eventData.status);
              if (onStatusChange) onStatusChange(eventData.status);
            }
            if (eventData.last_seen_at) {
              setLastSeen(eventData.last_seen_at);
            }
            if (eventData.data_sources && Array.isArray(eventData.data_sources)) {
              setDataSources(eventData.data_sources);
            }
            const isMetadataProfiled =
              eventData.event === 'METADATA_PROFILED' ||
              eventData.event_type === 'METADATA_PROFILED';
            if (isMetadataProfiled && onMetadataProfiled) {
              onMetadataProfiled();
            }
          }
        );
      }
    } catch {
      // WS Fallback
    }

    // Polling fallback
    const pollInterval = setInterval(async () => {
      try {
        const updated = await agentService.getAgent(agent.id);
        if (updated) {
          if (updated.status !== status) {
            setStatus(updated.status);
            if (onStatusChange) onStatusChange(updated.status);
          }
          if (updated.last_seen_at) {
            setLastSeen(updated.last_seen_at);
          }
          if (updated.data_sources) {
            setDataSources(updated.data_sources);
          }
        }
      } catch {
        // Fallback catch
      }
    }, 4000);

    return () => {
      if (ws) ws.close();
      clearInterval(pollInterval);
    };
  }, [agent.id, agent.api_token, onStatusChange, onMetadataProfiled, status]);

  // Filter failing/unreachable data sources
  const failingSources = dataSources.filter(
    (ds) => (ds.status && ds.status !== 'healthy') || (ds.last_error && ds.last_error.length > 0)
  );

  const hasCredentialPlaceholders = failingSources.some((ds) =>
    (ds.last_error || '').toLowerCase().includes('placeholder')
  );

  return (
    <div className="p-6 rounded-none bg-black border border-zinc-800 backdrop-blur-xl space-y-5 shadow-2xl font-mono">
      {/* Agent Status Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-zinc-900 pb-4">
        <div className="flex items-center gap-4">
          <div
            className={`w-3.5 h-3.5 rounded-none transition-all ${
              isOnline
                ? 'bg-sky-400 shadow-[0_0_15px_#38bdf8] animate-pulse'
                : isDegraded
                ? 'bg-amber-400 shadow-[0_0_15px_#f59e0b] animate-pulse'
                : 'bg-zinc-600'
            }`}
          />
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-extrabold text-white uppercase tracking-wide font-sans">
                {agent.name}
              </h2>
              <span className="text-[10px] font-bold tracking-widest px-2.5 py-0.5 rounded-none uppercase bg-sky-400/10 text-sky-400 border border-sky-400/30">
                {agent.agent_identifier}
              </span>
              <span
                className={`text-[10px] font-bold tracking-widest px-2.5 py-0.5 rounded-none uppercase border ${
                  isOnline
                    ? 'bg-sky-400/15 text-sky-400 border-sky-400/40'
                    : isDegraded
                    ? 'bg-amber-400/15 text-amber-400 border-amber-500/40 animate-pulse'
                    : 'bg-zinc-800 text-zinc-400 border-zinc-700'
                }`}
              >
                STATUS: {status.toUpperCase()}
              </span>
            </div>
            <p className="text-xs text-zinc-400 font-mono mt-1">
              Version: <span className="text-zinc-200">{agent.version || '1.0.0'}</span>
              {lastSeen && (
                <span className="text-zinc-500 ml-4">
                  • Last Ping: {new Date(lastSeen).toLocaleTimeString()}
                </span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs text-zinc-400 font-mono">
          <div>
            Linked Sources: <strong className="text-white">{dataSources.length}</strong>
          </div>
          {failingSources.length > 0 && (
            <div className="text-amber-400 font-bold bg-amber-400/10 border border-amber-500/30 px-2.5 py-1">
              ⚠️ {failingSources.length} Failing
            </div>
          )}
        </div>
      </div>

      {/* Warning Callout Box for DEGRADED Status or Unfilled Credential Placeholders */}
      {(isDegraded || failingSources.length > 0) && (
        <div className="p-5 rounded-none bg-amber-500/10 border border-amber-500/40 space-y-3 font-mono text-xs shadow-[0_0_20px_rgba(245,158,11,0.1)]">
          <div className="flex items-center gap-2 font-bold text-amber-300 uppercase tracking-wider text-sm">
            <span>⚠️</span>
            <span>
              {hasCredentialPlaceholders
                ? 'UNFILLED CREDENTIAL PLACEHOLDERS DETECTED'
                : 'DATABASE CONNECTION WARNING / DEGRADED AGENT'}
            </span>
          </div>

          <p className="text-zinc-300 text-xs leading-relaxed">
            {hasCredentialPlaceholders
              ? 'Your Docker agent started, but one or more database connection URLs contain unfilled placeholder credentials (e.g. <SRC_SRC_DB_1_PASSWORD> or <password>). Schema profiling cannot run until valid credentials are provided.'
              : 'One or more connected databases are unreachable by the Docker Agent. Please verify your connection credentials and network access.'}
          </p>

          {/* Failing Data Sources Detailed Error List */}
          <div className="space-y-2 pt-1 border-t border-amber-500/20">
            <span className="text-[10px] font-bold text-amber-400/90 uppercase block">
              DIAGNOSTIC ERROR DETAILS ({failingSources.length} DATABASES):
            </span>
            <div className="space-y-1.5">
              {failingSources.map((ds) => (
                <div
                  key={ds.id}
                  className="p-3 bg-black/80 border border-amber-500/30 text-amber-200/90 text-xs space-y-0.5"
                >
                  <div className="flex items-center justify-between font-bold">
                    <span className="text-white uppercase">{ds.name} ({ds.identifier})</span>
                    <span className="text-[10px] text-amber-400 uppercase border border-amber-500/40 px-2 py-0.2">
                      {ds.status || 'UNREACHABLE'}
                    </span>
                  </div>
                  {ds.last_error && (
                    <p className="text-[11px] text-amber-300/90 font-mono whitespace-pre-wrap mt-1">
                      {ds.last_error}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Remediation Tip */}
          <div className="p-3 bg-zinc-950 border border-zinc-800 text-[11px] text-sky-400 font-mono space-y-1">
            <span className="font-bold text-white uppercase block">💡 How to Fix This:</span>
            <p className="text-zinc-300">
              Replace all placeholder values in your <code className="text-sky-400 font-bold">docker run</code> command (such as <code className="text-amber-300">&lt;SRC_SRC_DB_1_PASSWORD&gt;</code>) with actual database passwords and usernames, then re-run the docker command.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default AgentStatusBanner;
