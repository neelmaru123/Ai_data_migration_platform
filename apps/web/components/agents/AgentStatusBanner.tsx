'use client';

import React, { useState, useEffect } from 'react';
import { AgentDetailResponse } from '../../types/agent';
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

  const isOnline = status === 'online';

  useEffect(() => {
    setStatus(agent.status || 'offline');
    setLastSeen(agent.last_seen_at || null);
  }, [agent.status, agent.last_seen_at]);

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
        }
      } catch {
        // Fallback catch
      }
    }, 5000);

    return () => {
      if (ws) ws.close();
      clearInterval(pollInterval);
    };
  }, [agent.id, agent.api_token, onStatusChange, onMetadataProfiled, status]);

  return (
    <div className="p-5 rounded-none bg-black border border-zinc-800 backdrop-blur-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-xl">
      <div className="flex items-center gap-4">
        <div
          className={`w-3 h-3 rounded-none transition-all ${
            isOnline
              ? 'bg-sky-400 shadow-[0_0_12px_#38bdf8] animate-pulse'
              : 'bg-zinc-600'
          }`}
        />
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-base font-bold text-white uppercase tracking-wider font-sans">
              {agent.name}
            </h2>
            <span className="text-[10px] font-mono font-bold tracking-widest px-2.5 py-0.5 rounded-none uppercase bg-sky-400/10 text-sky-400 border border-sky-400/30">
              {agent.agent_identifier}
            </span>
          </div>
          <p className="text-xs text-zinc-400 font-mono mt-0.5">
            Agent Status:{' '}
            <span className={isOnline ? 'text-sky-400 font-bold' : 'text-zinc-500'}>
              {status.toUpperCase()}
            </span>
            {lastSeen && (
              <span className="text-zinc-500 ml-3">
                • Last Ping: {new Date(lastSeen).toLocaleTimeString()}
              </span>
            )}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4 font-mono text-xs text-zinc-400 border-t sm:border-t-0 border-zinc-800 pt-3 sm:pt-0 w-full sm:w-auto justify-between">
        <div>
          <span className="text-white font-bold">{agent.data_sources?.length || 0}</span> Linked Data Sources
        </div>
      </div>
    </div>
  );
};

export default AgentStatusBanner;
