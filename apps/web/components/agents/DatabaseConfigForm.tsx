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
  hex: string;
  border: string;
}[] = [
  {
    type: 'postgresql',
    name: 'PostgreSQL',
    category: 'database',
    icon: Database,
    color: 'bg-sky-400/10 text-sky-400',
    hex: '#38bdf8',
    border: 'border-sky-400/30',
  },
  {
    type: 'mysql',
    name: 'MySQL',
    category: 'database',
    icon: Server,
    color: 'bg-amber-400/10 text-amber-400',
    hex: '#fbbf24',
    border: 'border-amber-400/30',
  },
  {
    type: 'mongodb',
    name: 'MongoDB',
    category: 'database',
    icon: HardDrive,
    color: 'bg-emerald-400/10 text-emerald-400',
    hex: '#34d399',
    border: 'border-emerald-400/30',
  },
  {
    type: 'csv',
    name: 'CSV File',
    category: 'file',
    icon: FileText,
    color: 'bg-purple-400/10 text-purple-400',
    hex: '#c084fc',
    border: 'border-purple-400/30',
  },
  {
    type: 'excel',
    name: 'Excel Sheet',
    category: 'file',
    icon: FileSpreadsheet,
    color: 'bg-teal-400/10 text-teal-400',
    hex: '#2dd4bf',
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

  // Helper to get hex color for a given engine type
  const getEngineHex = (typeStr: string): string => {
    const found = SUPPORTED_ENGINES.find((e) => e.type === typeStr);
    return found ? found.hex : '#38bdf8';
  };

  // SVG layout metrics for 3-column split wires
  const svgW = 160;
  const cardEstimateH = 320; // Estimated height per source config card
  const gap = 20;
  const cardsTotalH = sourceCount * cardEstimateH + (sourceCount - 1) * gap;
  const totalH = Math.max(340, cardsTotalH);
  const destY = totalH / 2;
  const mergeX = sourceCount === 1 ? svgW : 110;

  // Generate smooth organic wires matching each selected source engine's hex color
  const wires = sources.map((src, i) => {
    const startY = i * (cardEstimateH + gap) + cardEstimateH / 2;
    const hex = getEngineHex(src.type);

    if (sourceCount === 1 || Math.abs(startY - destY) < 1) {
      return {
        id: `form-wire-${i}`,
        d: `M 0 ${startY} L ${svgW} ${destY}`,
        startY,
        hex,
        duration: '1.2s',
        delay: '0s',
      };
    }

    const ctrl1X = 45;
    const ctrl1Y = startY;
    const ctrl2X = mergeX - 25;
    const ctrl2Y = destY;

    return {
      id: `form-wire-${i}`,
      d: `M 0 ${startY} C ${ctrl1X} ${ctrl1Y}, ${ctrl2X} ${ctrl2Y}, ${mergeX} ${destY}`,
      startY,
      hex,
      duration: `${1.2 + (i % 3) * 0.2}s`,
      delay: `${i * 0.15}s`,
    };
  });

  const mergedPathD = `M ${mergeX} ${destY} L ${svgW} ${destY}`;
  const destHex = getEngineHex(destination.type);

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-6xl mx-auto space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-none text-[11px] font-mono font-bold uppercase tracking-widest bg-sky-400/10 text-sky-400 border border-sky-400/30">
          STEP 2 OF 3: CONFIGURE ENGINES & AGENT
        </div>
        <h2 className="text-3xl font-extrabold text-white tracking-tight sm:text-4xl uppercase font-sans">
          Select Source & Destination Engines
        </h2>
        <p className="text-zinc-400 text-xs sm:text-sm max-w-2xl mx-auto leading-relaxed">
          Configure engine details for your {sourceCount} source {sourceCount === 1 ? 'database' : 'databases'}{' '}
          and 1 destination database.
        </p>
      </div>

      {/* Agent Metadata Block */}
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

      {/* 3-Column Split Form Layout with Dynamic Engine-Colored Pipeline Wires */}
      <div className="p-6 rounded-none bg-black border border-sky-400/30 space-y-4 shadow-2xl relative overflow-hidden">
        {/* Subtle grid background */}
        <div className="absolute inset-0 bg-[radial-gradient(#38bdf8_1px,transparent_1px)] [background-size:16px_16px] opacity-5 pointer-events-none" />

        {/* 3-Column Grid */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-0 items-start py-2">
          {/* Left Column: Source Databases Form Cards */}
          <div className="md:col-span-5 flex flex-col justify-start space-y-4">
            <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-zinc-400 mb-2 flex items-center gap-1.5 h-[18px]">
              <span className="w-2 h-2 bg-sky-400 rounded-none inline-block"></span>
              Source Database Engines ({sourceCount})
            </div>

            <div className="space-y-5">
              {sources.map((source, index) => {
                const currentEngineHex = getEngineHex(source.type);

                return (
                  <div
                    key={index}
                    className="p-5 rounded-none bg-zinc-950 border border-zinc-800 space-y-4 relative transition-all"
                    style={{ borderColor: `${currentEngineHex}50` }}
                  >
                    {/* Header */}
                    <div className="flex items-center justify-between">
                      <span
                        className="text-[10px] font-mono font-bold tracking-widest px-2.5 py-0.5 rounded-none uppercase border"
                        style={{
                          backgroundColor: `${currentEngineHex}15`,
                          color: currentEngineHex,
                          borderColor: `${currentEngineHex}40`,
                        }}
                      >
                        SOURCE #{index + 1}
                      </span>
                      <span className="text-[10px] text-zinc-400 font-mono">{source.identifier}</span>
                    </div>

                    {/* Inputs */}
                    <div className="space-y-3">
                      <div>
                        <label className="block text-[10px] font-mono font-semibold uppercase tracking-wider text-zinc-400 mb-1">
                          Source Name
                        </label>
                        <input
                          type="text"
                          required
                          value={source.name}
                          onChange={(e) => handleSourceChange(index, 'name', e.target.value)}
                          placeholder={`Primary DB ${index + 1}`}
                          className="w-full px-3 py-2 rounded-none bg-black border border-zinc-800 text-white text-xs placeholder-zinc-600 focus:outline-none focus:border-sky-400 transition-colors font-sans"
                        />
                      </div>

                      <div>
                        <label className="block text-[10px] font-mono font-semibold uppercase tracking-wider text-zinc-400 mb-1">
                          Identifier Tag
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
                          className="w-full px-3 py-2 rounded-none bg-black border border-zinc-800 text-sky-400 font-mono text-xs focus:outline-none focus:border-sky-400 transition-colors"
                        />
                      </div>
                    </div>

                    {/* Engine Selector Tiles */}
                    <div>
                      <label className="block text-[10px] font-mono font-semibold uppercase tracking-wider text-zinc-400 mb-2">
                        Database Engine
                      </label>
                      <div className="grid grid-cols-2 sm:grid-cols-5 gap-1.5">
                        {SUPPORTED_ENGINES.map((engine) => {
                          const EngineIcon = engine.icon;
                          const isSelected = source.type === engine.type;

                          return (
                            <button
                              key={engine.type}
                              type="button"
                              onClick={() => handleSourceChange(index, 'type', engine.type)}
                              className={`p-2 rounded-none border flex flex-col items-center gap-1 transition-all ${
                                isSelected
                                  ? `${engine.color} ${engine.border} bg-black shadow-md scale-[1.02]`
                                  : 'bg-black/60 border-zinc-800 text-zinc-500 hover:border-zinc-700 hover:text-white'
                              }`}
                            >
                              <EngineIcon className="w-4 h-4" />
                              <span className="text-[9px] font-semibold uppercase font-mono">{engine.name}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Middle Column: Dynamic Animated Engine-Colored Wires SVG */}
          <div className="md:col-span-2 flex flex-col justify-start items-center">
            <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-sky-400 mb-2 h-[18px] flex items-center justify-center animate-pulse">
              Engine Streams
            </div>

            <div style={{ height: `${totalH}px` }} className="w-full relative">
              <svg
                style={{ height: `${totalH}px` }}
                viewBox={`0 0 ${svgW} ${totalH}`}
                className="w-full overflow-visible"
                preserveAspectRatio="none"
              >
                <defs>
                  <filter id="form-neon-glow" x="-30%" y="-30%" width="160%" height="160%">
                    <feGaussianBlur stdDeviation="3" result="blur" />
                    <feMerge>
                      <feMergeNode in="blur" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>

                {/* Layer 1: Dark Track Lines */}
                {wires.map((w) => (
                  <path
                    key={`track-${w.id}`}
                    d={w.d}
                    stroke="#18181b"
                    strokeWidth="4"
                    fill="none"
                  />
                ))}
                {sourceCount > 1 && (
                  <path
                    d={mergedPathD}
                    stroke="#18181b"
                    strokeWidth="5"
                    fill="none"
                  />
                )}

                {/* Layer 2: Dynamic Engine-Colored Laser Lines */}
                {wires.map((w) => (
                  <path
                    key={`laser-${w.id}`}
                    d={w.d}
                    stroke={w.hex}
                    strokeWidth="2.2"
                    fill="none"
                    filter="url(#form-neon-glow)"
                  />
                ))}
                {sourceCount > 1 && (
                  <path
                    d={mergedPathD}
                    stroke={destHex}
                    strokeWidth="3"
                    fill="none"
                    filter="url(#form-neon-glow)"
                  />
                )}

                {/* Layer 3: Anchor Dots & Flowing Particles */}
                {wires.map((w) => (
                  <g key={`particle-${w.id}`}>
                    <circle
                      cx={0}
                      cy={w.startY}
                      r="4.5"
                      fill={w.hex}
                      stroke="#ffffff"
                      strokeWidth="1"
                      filter="url(#form-neon-glow)"
                    />
                    <circle r="3.5" fill="#ffffff" filter="url(#form-neon-glow)">
                      <animateMotion
                        path={w.d}
                        dur={w.duration}
                        begin={w.delay}
                        repeatCount="indefinite"
                      />
                    </circle>
                  </g>
                ))}

                {/* Junction Node */}
                {sourceCount > 1 && (
                  <g transform={`translate(${mergeX}, ${destY})`}>
                    <circle
                      r="5.5"
                      fill="#000000"
                      stroke={destHex}
                      strokeWidth="2"
                      filter="url(#form-neon-glow)"
                    />
                    <circle r="2.5" fill={destHex} className="animate-ping" />
                  </g>
                )}

                {/* Merged Stream Flow Particle */}
                {sourceCount > 1 && (
                  <circle r="4" fill="#ffffff" filter="url(#form-neon-glow)">
                    <animateMotion
                      path={mergedPathD}
                      dur="0.8s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}

                {/* Destination Target Anchor Dot */}
                <circle
                  cx={svgW}
                  cy={destY}
                  r="5"
                  fill={destHex}
                  stroke="#ffffff"
                  strokeWidth="1"
                  filter="url(#form-neon-glow)"
                />
              </svg>
            </div>
          </div>

          {/* Right Column: Destination Database Form Card */}
          <div className="md:col-span-5 flex flex-col justify-start">
            <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-zinc-400 mb-2 flex items-center gap-1.5 h-[18px]">
              <span className="w-2 h-2 bg-blue-500 rounded-none inline-block"></span>
              Target Destination Sink (1)
            </div>

            <div
              style={{ height: `${totalH}px` }}
              className="p-5 rounded-none bg-zinc-950 border border-blue-500/50 flex flex-col justify-between shadow-[0_0_20px_rgba(59,130,246,0.15)] relative"
            >
              <div className="flex items-center justify-between">
                <span
                  className="text-[10px] font-mono font-bold tracking-widest px-2.5 py-0.5 rounded-none uppercase border"
                  style={{
                    backgroundColor: `${destHex}15`,
                    color: destHex,
                    borderColor: `${destHex}40`,
                  }}
                >
                  TARGET SINK
                </span>
                <span className="text-[10px] text-zinc-400 font-mono">{destination.identifier}</span>
              </div>

              <div className="space-y-3 my-2">
                <div>
                  <label className="block text-[10px] font-mono font-semibold uppercase tracking-wider text-zinc-400 mb-1">
                    Destination Name
                  </label>
                  <input
                    type="text"
                    required
                    value={destination.name}
                    onChange={(e) => setDestination({ ...destination, name: e.target.value })}
                    placeholder="Target Data Warehouse"
                    className="w-full px-3 py-2 rounded-none bg-black border border-zinc-800 text-white text-xs placeholder-zinc-600 focus:outline-none focus:border-blue-400 transition-colors font-sans"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-mono font-semibold uppercase tracking-wider text-zinc-400 mb-1">
                    Destination Identifier Tag
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
                    className="w-full px-3 py-2 rounded-none bg-black border border-zinc-800 text-blue-400 font-mono text-xs focus:outline-none focus:border-blue-400 transition-colors"
                  />
                </div>
              </div>

              {/* Engine Selector Tiles for Destination */}
              <div>
                <label className="block text-[10px] font-mono font-semibold uppercase tracking-wider text-zinc-400 mb-2">
                  Destination Database Engine
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-1.5">
                  {SUPPORTED_ENGINES.map((engine) => {
                    const EngineIcon = engine.icon;
                    const isSelected = destination.type === engine.type;

                    return (
                      <button
                        key={engine.type}
                        type="button"
                        onClick={() => setDestination({ ...destination, type: engine.type })}
                        className={`p-2 rounded-none border flex flex-col items-center gap-1 transition-all ${
                          isSelected
                            ? `${engine.color} ${engine.border} bg-black shadow-md scale-[1.02]`
                            : 'bg-black/60 border-zinc-800 text-zinc-500 hover:border-zinc-700 hover:text-white'
                        }`}
                      >
                        <EngineIcon className="w-4 h-4" />
                        <span className="text-[9px] font-semibold uppercase font-mono">{engine.name}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="pt-3 border-t border-zinc-900 flex items-center justify-between text-[10px] font-mono text-zinc-400">
                <span>Sink Target: {destination.type.toUpperCase()}</span>
                <span style={{ color: destHex }} className="uppercase font-bold">
                  Configured
                </span>
              </div>
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
