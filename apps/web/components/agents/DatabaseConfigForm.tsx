'use client';

import React, { useState } from 'react';
import { InitialDataSourceCreate, ValidSourceType } from '../../types/agent';
import {
  ArrowLeft,
  ArrowRight,
  Database,
  FileSpreadsheet,
  FileText,
  HardDrive,
  Server,
} from 'lucide-react';

interface DatabaseConfigFormProps {
  sourceCount: number;
  onSubmit: (formData: {
    agentName: string;
    agentIdentifier: string;
    sources: InitialDataSourceCreate[];
    destination: InitialDataSourceCreate;
  }) => void;
  onBack: () => void;
  isSubmitting?: boolean;
}

export const SUPPORTED_ENGINES: {
  type: ValidSourceType;
  name: string;
  category: 'database' | 'file';
  icon: any;
  color: string;
  border: string;
}[] = [
  {
    type: 'postgresql',
    name: 'PostgreSQL',
    category: 'database',
    icon: Database,
    color: 'bg-sky-400/10 text-sky-400',
    border: 'border-sky-400/30',
  },
  {
    type: 'mysql',
    name: 'MySQL',
    category: 'database',
    icon: Server,
    color: 'bg-amber-400/10 text-amber-400',
    border: 'border-amber-400/30',
  },
  {
    type: 'mongodb',
    name: 'MongoDB',
    category: 'database',
    icon: HardDrive,
    color: 'bg-emerald-400/10 text-emerald-400',
    border: 'border-emerald-400/30',
  },
  {
    type: 'csv',
    name: 'CSV File',
    category: 'file',
    icon: FileText,
    color: 'bg-purple-400/10 text-purple-400',
    border: 'border-purple-400/30',
  },
  {
    type: 'excel',
    name: 'Excel Sheet',
    category: 'file',
    icon: FileSpreadsheet,
    color: 'bg-teal-400/10 text-teal-400',
    border: 'border-teal-400/30',
  },
];

export const DatabaseConfigForm: React.FC<DatabaseConfigFormProps> = ({
  sourceCount,
  onSubmit,
  onBack,
  isSubmitting = false,
}) => {
  const [agentName, setAgentName] = useState('Production Migration Agent');
  const [agentIdentifier, setAgentIdentifier] = useState(
    `agent_${Math.random().toString(36).substring(2, 7)}`
  );

  // Initialize N sources
  const [sources, setSources] = useState<InitialDataSourceCreate[]>(() =>
    Array.from({ length: sourceCount }).map((_, idx) => ({
      name: `Source Database ${idx + 1}`,
      type: idx === 0 ? 'postgresql' : idx === 1 ? 'mysql' : 'mongodb',
      role: 'source',
      identifier: `src_db_${idx + 1}`,
    }))
  );

  // Initialize 1 destination
  const [destination, setDestination] = useState<InitialDataSourceCreate>({
    name: 'Target Destination Database',
    type: 'postgresql',
    role: 'target',
    identifier: 'dst_db_main',
  });

  const handleSourceChange = (
    index: number,
    field: keyof InitialDataSourceCreate,
    value: string
  ) => {
    const updated = [...sources];
    updated[index] = { ...updated[index], [field]: value };
    setSources(updated);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      agentName: agentName.trim(),
      agentIdentifier: agentIdentifier.trim(),
      sources,
      destination,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-5xl mx-auto space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-none text-[11px] font-mono font-bold uppercase tracking-widest bg-sky-400/10 text-sky-400 border border-sky-400/30">
          STEP 2 OF 3: CONFIGURE ENGINES & AGENT
        </div>
        <h2 className="text-3xl font-extrabold text-white tracking-tight sm:text-4xl uppercase font-sans">
          Select Source & Destination Engines
        </h2>
        <p className="text-zinc-400 text-xs sm:text-sm max-w-2xl mx-auto leading-relaxed">
          Configure details for your {sourceCount} source {sourceCount === 1 ? 'database' : 'databases'}{' '}
          and 1 destination database.
        </p>
      </div>

      {/* Agent Credentials Block */}
      <div className="p-6 rounded-none bg-black border border-zinc-800 backdrop-blur-xl space-y-4 shadow-xl">
        <div>
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">Docker Agent Metadata</h3>
          <p className="text-xs text-zinc-400 font-mono">
            Identity details used to register your Docker agent process on the control plane.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
          <div>
            <label className="block text-[11px] font-mono font-semibold uppercase tracking-wider text-zinc-300 mb-1">
              Agent Name
            </label>
            <input
              type="text"
              required
              value={agentName}
              onChange={(e) => setAgentName(e.target.value)}
              placeholder="e.g. Production Migration Agent"
              className="w-full px-4 py-2.5 rounded-none bg-sky-400/[0.04] border border-sky-400/30 text-white text-xs placeholder-zinc-500 focus:outline-none focus:border-sky-400 transition-colors font-sans"
            />
          </div>
          <div>
            <label className="block text-[11px] font-mono font-semibold uppercase tracking-wider text-zinc-300 mb-1">
              Unique Agent Identifier
            </label>
            <input
              type="text"
              required
              value={agentIdentifier}
              onChange={(e) => setAgentIdentifier(e.target.value.toLowerCase().replace(/\s+/g, '_'))}
              placeholder="e.g. agent_prod_001"
              className="w-full px-4 py-2.5 rounded-none bg-sky-400/[0.04] border border-sky-400/30 text-sky-400 font-mono text-xs focus:outline-none focus:border-sky-400 transition-colors"
            />
          </div>
        </div>
      </div>

      {/* Sources Grid */}
      <div className="space-y-4">
        <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider flex items-center gap-2">
          <span className="w-2 h-2 rounded-none bg-sky-400"></span>
          Source Databases ({sources.length})
        </h3>

        <div className="grid grid-cols-1 gap-5">
          {sources.map((source, index) => (
            <div
              key={index}
              className="p-6 rounded-none bg-black border border-zinc-800 backdrop-blur-xl space-y-4"
            >
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono font-bold tracking-widest px-3 py-1 rounded-none bg-sky-400/10 text-sky-400 border border-sky-400/30">
                  SOURCE #{index + 1}
                </span>
                <span className="text-xs text-zinc-400 font-mono">{source.identifier}</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[11px] font-mono font-semibold uppercase tracking-wider text-zinc-300 mb-1">
                    Source Name
                  </label>
                  <input
                    type="text"
                    required
                    value={source.name}
                    onChange={(e) => handleSourceChange(index, 'name', e.target.value)}
                    placeholder={`e.g. Primary DB ${index + 1}`}
                    className="w-full px-4 py-2.5 rounded-none bg-sky-400/[0.04] border border-sky-400/30 text-white text-xs placeholder-zinc-500 focus:outline-none focus:border-sky-400 transition-colors font-sans"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-mono font-semibold uppercase tracking-wider text-zinc-300 mb-1">
                    Source Tag / Identifier
                  </label>
                  <input
                    type="text"
                    required
                    value={source.identifier}
                    onChange={(e) =>
                      handleSourceChange(
                        index,
                        'identifier',
                        e.target.value.toLowerCase().replace(/\s+/g, '_')
                      )
                    }
                    className="w-full px-4 py-2.5 rounded-none bg-sky-400/[0.04] border border-sky-400/30 text-sky-400 font-mono text-xs focus:outline-none focus:border-sky-400 transition-colors"
                  />
                </div>
              </div>

              {/* Engine Selector Tiles */}
              <div>
                <label className="block text-[11px] font-mono font-semibold uppercase tracking-wider text-zinc-300 mb-2">
                  Select Database Engine Type
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                  {SUPPORTED_ENGINES.map((engine) => {
                    const EngineIcon = engine.icon;
                    const isSelected = source.type === engine.type;

                    return (
                      <button
                        key={engine.type}
                        type="button"
                        onClick={() => handleSourceChange(index, 'type', engine.type)}
                        className={`p-3 rounded-none border flex flex-col items-center gap-2 transition-all ${
                          isSelected
                            ? `${engine.color} ${engine.border} bg-zinc-950 shadow-md scale-[1.02]`
                            : 'bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-white'
                        }`}
                      >
                        <EngineIcon className="w-5 h-5" />
                        <span className="text-xs font-semibold uppercase font-mono text-[11px]">{engine.name}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Destination Block */}
      <div className="space-y-4">
        <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider flex items-center gap-2">
          <span className="w-2 h-2 rounded-none bg-blue-500"></span>
          Destination Database (1)
        </h3>

        <div className="p-6 rounded-none bg-black border border-blue-500/40 backdrop-blur-xl space-y-4 shadow-[0_0_20px_rgba(59,130,246,0.1)]">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono font-bold tracking-widest px-3 py-1 rounded-none bg-blue-500/10 text-blue-400 border border-blue-500/30">
              TARGET SINK
            </span>
            <span className="text-xs text-zinc-400 font-mono">{destination.identifier}</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-mono font-semibold uppercase tracking-wider text-zinc-300 mb-1">
                Destination Name
              </label>
              <input
                type="text"
                required
                value={destination.name}
                onChange={(e) => setDestination({ ...destination, name: e.target.value })}
                placeholder="e.g. Target Data Warehouse"
                className="w-full px-4 py-2.5 rounded-none bg-sky-400/[0.04] border border-sky-400/30 text-white text-xs placeholder-zinc-500 focus:outline-none focus:border-blue-400 transition-colors font-sans"
              />
            </div>
            <div>
              <label className="block text-[11px] font-mono font-semibold uppercase tracking-wider text-zinc-300 mb-1">
                Destination Identifier
              </label>
              <input
                type="text"
                required
                value={destination.identifier}
                onChange={(e) =>
                  setDestination({
                    ...destination,
                    identifier: e.target.value.toLowerCase().replace(/\s+/g, '_'),
                  })
                }
                className="w-full px-4 py-2.5 rounded-none bg-sky-400/[0.04] border border-sky-400/30 text-blue-400 font-mono text-xs focus:outline-none focus:border-blue-400 transition-colors"
              />
            </div>
          </div>

          {/* Engine Selector Tiles for Destination */}
          <div>
            <label className="block text-[11px] font-mono font-semibold uppercase tracking-wider text-zinc-300 mb-2">
              Select Destination Engine Type
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              {SUPPORTED_ENGINES.map((engine) => {
                const EngineIcon = engine.icon;
                const isSelected = destination.type === engine.type;

                return (
                  <button
                    key={engine.type}
                    type="button"
                    onClick={() => setDestination({ ...destination, type: engine.type })}
                    className={`p-3 rounded-none border flex flex-col items-center gap-2 transition-all ${
                      isSelected
                        ? `${engine.color} ${engine.border} bg-zinc-950 shadow-md scale-[1.02]`
                        : 'bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-white'
                    }`}
                  >
                    <EngineIcon className="w-5 h-5" />
                    <span className="text-xs font-semibold uppercase font-mono text-[11px]">{engine.name}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-between pt-4">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-2 py-3 px-6 rounded-none bg-zinc-900 hover:bg-zinc-800 text-zinc-300 text-xs font-bold uppercase tracking-wider border border-zinc-800 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Topology
        </button>

        <button
          type="submit"
          disabled={isSubmitting}
          className="inline-flex items-center gap-2 py-3 px-8 rounded-none bg-sky-400 hover:bg-sky-300 text-black text-xs font-bold uppercase tracking-wider transition-colors shadow-lg shadow-sky-950/50 hover:scale-[1.01] disabled:opacity-50"
        >
          {isSubmitting ? (
            <>
              <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-none animate-spin"></div>
              <span>Registering Agent...</span>
            </>
          ) : (
            <>
              <span>Generate Docker Command</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>
    </form>
  );
};

export default DatabaseConfigForm;
