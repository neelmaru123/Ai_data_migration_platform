'use client';

import React from 'react';
import { TopologyType } from '../../types/agent';
import {
  ArrowRight,
  CheckCircle2,
} from 'lucide-react';

interface TopologySelectorProps {
  selectedTopology: TopologyType;
  customSourceCount: number;
  onSelectTopology: (topology: TopologyType) => void;
  onCustomSourceCountChange: (count: number) => void;
  onNext: () => void;
}

export const TOPOLOGY_OPTIONS = [
  {
    id: '1:1' as TopologyType,
    title: '1 to 1 Direct',
    subtitle: '1 Source → 1 Destination',
    description: 'Single source database directly mapped and streamed to one target database.',
    sourceCount: 1,
    badge: 'DIRECT MAPPING',
  },
  {
    id: '2:1' as TopologyType,
    title: '2 to 1 Merge',
    subtitle: '2 Sources → 1 Destination',
    description: 'Unify and consolidate 2 distinct source databases into a central destination engine.',
    sourceCount: 2,
    badge: 'CONSOLIDATION',
  },
  {
    id: '3:1' as TopologyType,
    title: '3 to 1 Multi-Merge',
    subtitle: '3 Sources → 1 Destination',
    description: 'Aggregate data pipelines from 3 separate databases into a unified target schema.',
    sourceCount: 3,
    badge: 'MULTI-SOURCE',
  },
  {
    id: 'custom' as TopologyType,
    title: 'Custom (N to 1)',
    subtitle: 'N Sources → 1 Destination',
    description: 'Configure custom multi-source aggregation topology for enterprise architectures.',
    sourceCount: 4,
    badge: 'ENTERPRISE',
  },
];

export const TopologySelector: React.FC<TopologySelectorProps> = ({
  selectedTopology,
  customSourceCount,
  onSelectTopology,
  onCustomSourceCountChange,
  onNext,
}) => {
  const currentOption =
    TOPOLOGY_OPTIONS.find((opt) => opt.id === selectedTopology) || TOPOLOGY_OPTIONS[1];

  const sourceCount =
    selectedTopology === 'custom' ? customSourceCount : currentOption.sourceCount;

  // Exact Pixel Layout Math for 100% Alignment:
  // Each source card: Height = 64px, Gap = 12px -> Pitch = 76px.
  const cardH = 64;
  const gap = 12;
  const pitch = cardH + gap;
  const cardsTotalH = sourceCount * cardH + (sourceCount - 1) * gap;
  const totalH = Math.max(160, cardsTotalH);
  const destY = totalH / 2;

  const svgW = 160;
  const mergeX = sourceCount === 1 ? svgW : 110;

  // Generate Smooth Organic Cable Curves (NO 90-degree sharp rectangular angles)
  const branchPaths = Array.from({ length: sourceCount }).map((_, i) => {
    const startY = i * pitch + cardH / 2;

    // CASE 1: Single source (1:1) — straight horizontal line, full width
    if (sourceCount === 1) {
      return {
        id: `branch-${i}`,
        d: `M 0 ${startY} L ${svgW} ${destY}`,
        startY,
        duration: '1.2s',
        delay: '0s',
      };
    }

    // CASE 2: Middle wire where startY === destY (odd counts: 3:1, 5:1, 7:1, etc.)
    // Use a simple straight L line to svgW. A flat degenerate Bezier (all control
    // points at the same Y) causes browsers to fail rendering glow filters on it.
    if (Math.abs(startY - destY) < 1) {
      return {
        id: `branch-${i}`,
        d: `M 0 ${startY} L ${svgW} ${destY}`,
        startY,
        duration: '1.2s',
        delay: `${i * 0.15}s`,
      };
    }

    // CASE 3: Normal curved wire flowing gracefully into the junction point at (mergeX, destY)
    const ctrl1X = 45;
    const ctrl1Y = startY;
    const ctrl2X = mergeX - 25;
    const ctrl2Y = destY;

    return {
      id: `branch-${i}`,
      d: `M 0 ${startY} C ${ctrl1X} ${ctrl1Y}, ${ctrl2X} ${ctrl2Y}, ${mergeX} ${destY}`,
      startY,
      duration: `${1.2 + (i % 3) * 0.2}s`,
      delay: `${i * 0.15}s`,
    };
  });

  const mergedPathD = `M ${mergeX} ${destY} L ${svgW} ${destY}`;

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="text-center space-y-2">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-none text-[11px] font-mono font-bold uppercase tracking-widest bg-sky-400/10 text-sky-400 border border-sky-400/30">
          STEP 1 OF 3: TOPOLOGY DESIGNER
        </div>
        <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight uppercase font-sans">
          Select Migration Topology
        </h2>
        <p className="text-zinc-400 text-xs max-w-2xl mx-auto leading-relaxed">
          Choose your source-to-destination architecture below. Topology defines how many source databases you want to combine into a single destination database.
        </p>
        <div className="p-3 bg-zinc-950 border border-sky-400/20 max-w-xl mx-auto text-[11px] font-mono text-sky-300 text-left">
          💡 <strong>What is Topology?</strong>
          <span className="text-zinc-400 block mt-0.5">
            • <strong>1 to 1:</strong> Migrate 1 source DB directly into 1 target DB.<br />
            • <strong>2 to 1 / 3 to 1:</strong> Consolidate data from 2 or 3 separate DBs into 1 merged target DB.<br />
            • <strong>Custom:</strong> Merge N source DBs into 1 target DB.
          </span>
        </div>
      </div>

      {/* Sharp Top Selector Tabs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 border border-zinc-800 bg-black p-1.5 rounded-none">
        {TOPOLOGY_OPTIONS.map((option) => {
          const isSelected = selectedTopology === option.id;

          return (
            <button
              key={option.id}
              type="button"
              onClick={() => onSelectTopology(option.id)}
              className={`p-3 rounded-none text-left transition-all border ${
                isSelected
                  ? 'bg-sky-400/15 border-sky-400 text-white shadow-[0_0_20px_rgba(56,189,248,0.25)]'
                  : 'bg-zinc-950/80 border-zinc-900 text-zinc-400 hover:border-zinc-800 hover:text-zinc-200'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-sky-400">
                  {option.id}
                </span>
                {isSelected && <CheckCircle2 className="w-3.5 h-3.5 text-sky-400" />}
              </div>
              <div className="text-xs font-bold text-white uppercase tracking-wider">{option.title}</div>
              <div className="text-[10px] text-zinc-500 font-mono mt-0.5">{option.subtitle}</div>
            </button>
          );
        })}
      </div>

      {/* Custom Count Picker if 'custom' selected */}
      {selectedTopology === 'custom' && (
        <div className="p-3.5 rounded-none bg-zinc-950 border border-sky-400/30 flex flex-col sm:flex-row items-center justify-between gap-3 animate-fadeIn">
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-white">Custom Source Count</h4>
            <p className="text-[11px] text-zinc-400 font-mono">
              Specify exact number of source database engines to merge into destination.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => onCustomSourceCountChange(Math.max(1, customSourceCount - 1))}
              className="w-8 h-8 rounded-none bg-zinc-900 hover:bg-zinc-800 text-white font-bold transition-colors flex items-center justify-center border border-zinc-800 text-sm"
            >
              -
            </button>
            <span className="w-10 text-center font-mono font-bold text-base text-sky-400">
              {customSourceCount}
            </span>
            <button
              type="button"
              onClick={() => onCustomSourceCountChange(Math.min(10, customSourceCount + 1))}
              className="w-8 h-8 rounded-none bg-zinc-900 hover:bg-zinc-800 text-white font-bold transition-colors flex items-center justify-center border border-zinc-800 text-sm"
            >
              +
            </button>
          </div>
        </div>
      )}

      {/* Compact Interactive Topology Canvas */}
      <div className="p-5 rounded-none bg-black border border-sky-400/30 space-y-4 shadow-2xl relative overflow-hidden">
        {/* Subtle grid background */}
        <div className="absolute inset-0 bg-[radial-gradient(#38bdf8_1px,transparent_1px)] [background-size:16px_16px] opacity-5 pointer-events-none" />

        {/* Diagram Title */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between border-b border-zinc-800 pb-3 gap-2">
          <div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              {currentOption.title} Pipeline Architecture
            </h3>
            <p className="text-[11px] text-zinc-400 font-mono mt-0.5">{currentOption.description}</p>
          </div>

          <span className="text-[10px] font-mono font-bold tracking-widest px-2.5 py-0.5 rounded-none bg-sky-400/10 text-sky-400 border border-sky-400/30">
            {currentOption.badge}
          </span>
        </div>

        {/* 3-Column Aligned Layout */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-0 items-start py-2">
          {/* Left Column: Source Cards Container */}
          <div className="md:col-span-5 flex flex-col justify-start">
            <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-zinc-400 mb-2 flex items-center gap-1.5 h-[18px]">
              <span className="w-2 h-2 bg-sky-400 rounded-none inline-block"></span>
              Source Data Engines ({sourceCount})
            </div>

            <div className="space-y-3">
              {Array.from({ length: sourceCount }).map((_, i) => (
                <div
                  key={i}
                  className="p-3 rounded-none bg-zinc-950 border border-sky-400/40 flex items-center justify-between shadow-[0_0_15px_rgba(56,189,248,0.1)] hover:border-sky-400 transition-all h-[64px]"
                >
                  <div className="flex items-center gap-3">
                    <div>
                      <div className="text-xs font-bold text-white uppercase tracking-wider">
                        Source Engine #{i + 1}
                      </div>
                      <div className="text-[10px] font-mono text-sky-400">
                        SRC_NODE_0{i + 1}
                      </div>
                    </div>
                  </div>

                  <span className="text-[9px] font-mono uppercase px-2 py-0.5 bg-zinc-900 text-zinc-400 border border-zinc-800">
                    Input
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Middle Column: Smooth Cable Wires SVG */}
          <div className="md:col-span-2 flex flex-col justify-start items-center">
            <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-sky-400 mb-2 h-[18px] flex items-center justify-center animate-pulse">
              Pipeline Wires
            </div>

            <div style={{ height: `${totalH}px` }} className="w-full relative">
              <svg
                style={{ height: `${totalH}px` }}
                viewBox={`0 0 ${svgW} ${totalH}`}
                className="w-full overflow-visible"
                preserveAspectRatio="none"
              >
                <defs>
                  <filter id="neon-wire-glow-filter" x="-30%" y="-30%" width="160%" height="160%">
                    <feGaussianBlur stdDeviation="3" result="blur" />
                    <feMerge>
                      <feMergeNode in="blur" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>

                {/* STEP 1: Render ALL dark background tracks first (Prevents Z-index overwrite bugs) */}
                {branchPaths.map((p) => (
                  <path
                    key={`track-${p.id}`}
                    d={p.d}
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

                {/* STEP 2: Render ALL glowing cyan laser wire lines second (Guarantees 100% vibrant color on ALL lines!) */}
                {branchPaths.map((p) => (
                  <path
                    key={`laser-${p.id}`}
                    d={p.d}
                    stroke="#38bdf8"
                    strokeWidth="2.2"
                    fill="none"
                    filter="url(#neon-wire-glow-filter)"
                  />
                ))}
                {sourceCount > 1 && (
                  <path
                    d={mergedPathD}
                    stroke="#38bdf8"
                    strokeWidth="3"
                    fill="none"
                    filter="url(#neon-wire-glow-filter)"
                  />
                )}

                {/* STEP 3: Render glowing anchor dots and animated data light particles */}
                {branchPaths.map((p) => (
                  <g key={`particle-${p.id}`}>
                    {/* Source Card Anchor Dot */}
                    <circle
                      cx={0}
                      cy={p.startY}
                      r="4.5"
                      fill="#38bdf8"
                      stroke="#7dd3fc"
                      strokeWidth="1.5"
                      filter="url(#neon-wire-glow-filter)"
                    />

                    {/* Flowing Light Packet Particle */}
                    <circle r="3.5" fill="#ffffff" filter="url(#neon-wire-glow-filter)">
                      <animateMotion
                        path={p.d}
                        dur={p.duration}
                        begin={p.delay}
                        repeatCount="indefinite"
                      />
                    </circle>
                  </g>
                ))}

                {/* Junction Hub Dot for Multi-Source (N > 1) */}
                {sourceCount > 1 && (
                  <g transform={`translate(${mergeX}, ${destY})`}>
                    <circle
                      r="5.5"
                      fill="#000000"
                      stroke="#38bdf8"
                      strokeWidth="2"
                      filter="url(#neon-wire-glow-filter)"
                    />
                    <circle r="2.5" fill="#38bdf8" className="animate-ping" />
                  </g>
                )}

                {/* Merged Stream Flow Particle (N > 1) */}
                {sourceCount > 1 && (
                  <circle r="4" fill="#ffffff" filter="url(#neon-wire-glow-filter)">
                    <animateMotion
                      path={mergedPathD}
                      dur="0.8s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}

                {/* Target Destination Anchor Dot */}
                <circle
                  cx={svgW}
                  cy={destY}
                  r="5"
                  fill="#38bdf8"
                  stroke="#7dd3fc"
                  strokeWidth="1.5"
                  filter="url(#neon-wire-glow-filter)"
                />
              </svg>
            </div>
          </div>

          {/* Right Column: Target Destination Card */}
          <div className="md:col-span-5 flex flex-col justify-start">
            <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-zinc-400 mb-2 flex items-center gap-1.5 h-[18px]">
              <span className="w-2 h-2 bg-blue-500 rounded-none inline-block"></span>
              Target Destination Sink (1)
            </div>

            <div
              style={{ height: `${totalH}px` }}
              className="p-5 rounded-none bg-zinc-950 border border-blue-500/50 flex flex-col justify-between shadow-[0_0_20px_rgba(59,130,246,0.15)] relative"
            >
              <div className="flex items-center gap-3">
                <div>
                  <div className="text-xs font-bold text-white uppercase tracking-wider">
                    Target Destination Node
                  </div>
                  <div className="text-[10px] font-mono text-blue-400">
                    DST_NODE_MAIN
                  </div>
                </div>
              </div>

              <p className="text-[11px] text-zinc-400 leading-relaxed font-mono">
                Receives consolidated dataset records from {sourceCount} {sourceCount === 1 ? 'source' : 'sources'} in deterministic streaming chunks.
              </p>

              <div className="pt-2 border-t border-zinc-900 flex items-center justify-between text-[10px] font-mono text-zinc-400">
                <span>Status: Ready for Config</span>
                <span className="text-blue-400 uppercase font-bold">Sink Target</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Next Button */}
      <div className="flex justify-end pt-2">
        <button
          type="button"
          onClick={onNext}
          className="inline-flex items-center gap-2 py-3.5 px-8 rounded-none bg-sky-400 hover:bg-sky-300 text-black text-xs font-bold uppercase tracking-wider transition-all shadow-lg shadow-sky-950/50 hover:scale-[1.01]"
        >
          <span>Configure Databases</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

export default TopologySelector;
