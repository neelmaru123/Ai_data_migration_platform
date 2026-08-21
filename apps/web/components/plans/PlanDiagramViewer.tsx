'use client';

import React, { useState } from 'react';
import { TransformationPlanAST, TableMappingSpec, ColumnMappingSpec } from '../../types/migrationPlan';

interface PlanDiagramViewerProps {
  ast: TransformationPlanAST;
}

export const PlanDiagramViewer: React.FC<PlanDiagramViewerProps> = ({ ast }) => {
  const tableNames = ast.table_mappings.map((tm) => tm.target_table_name);

  // Active target table filter (defaults to first table or 'all')
  const [selectedTableFilter, setSelectedTableFilter] = useState<string>(
    tableNames[0] || 'all'
  );

  // Filter mappings to display based on tab selection
  const activeMappings: TableMappingSpec[] =
    selectedTableFilter === 'all'
      ? ast.table_mappings
      : ast.table_mappings.filter((tm) => tm.target_table_name === selectedTableFilter);

  // Flatten all column-level mapping rows for the active table(s)
  interface ColumnFlowRow {
    id: string;
    targetTableName: string;
    targetColumnName: string;
    targetDataType: string;
    isPrimaryKey: boolean;
    transformationType: string;
    sourceIdentifier: string;
    sourceTableName: string;
    sourceColumnName: string;
    explanation: string;
  }

  const columnRows: ColumnFlowRow[] = [];

  activeMappings.forEach((tm) => {
    tm.column_mappings.forEach((cm, cIdx) => {
      const src = cm.source_columns[0] || {
        identifier: tm.source_tables[0]?.identifier || 'src',
        schema_name: 'public',
        table_name: tm.source_tables[0]?.table_name || tm.target_table_name,
        column_name: cm.target_column_name || 'N/A',
      };

      columnRows.push({
        id: `${tm.target_table_name}-${cm.target_column_name || cIdx}`,
        targetTableName: tm.target_table_name,
        targetColumnName: cm.target_column_name || '[Dropped Column]',
        targetDataType: cm.target_data_type || 'N/A',
        isPrimaryKey: cm.is_primary_key,
        transformationType: cm.transformation_type,
        sourceIdentifier: src.identifier,
        sourceTableName: src.table_name,
        sourceColumnName: src.column_name,
        explanation: cm.explanation,
      });
    });
  });

  // Canvas Geometry Specs
  const svgWidth = 1040;
  const rowHeight = 64;
  const rowGap = 16;
  const leftX = 260; // Source column box right edge
  const rightX = 740; // Target column box left edge
  const midX = (leftX + rightX) / 2;

  const totalRows = columnRows.length;
  const canvasHeight = Math.max(380, totalRows * (rowHeight + rowGap) + 40);

  return (
    <div className="w-full space-y-6 animate-fadeIn font-mono">
      {/* Visual Canvas Card */}
      <div className="p-6 rounded-none bg-black border border-zinc-800 backdrop-blur-xl shadow-2xl space-y-6">
        {/* Header & Table Filter Switcher */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
          <div>
            <span className="text-[10px] font-mono font-bold tracking-widest px-2.5 py-0.5 rounded-none uppercase bg-sky-400/10 text-sky-400 border border-sky-400/30">
              COLUMN-TO-COLUMN GRAPH TOPOLOGY
            </span>
            <h3 className="text-xl font-extrabold text-white uppercase font-sans tracking-wide mt-1">
              Field-Level Schema Transformation Pipes
            </h3>
            <p className="text-zinc-400 text-xs font-mono mt-0.5">
              Inspect exact source field to target field mappings, data types, and static transformation pipes.
            </p>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono text-zinc-400">
            <div className="flex items-center gap-2">
              <span className="w-3 h-0.5 bg-sky-400 inline-block" />
              <span>Direct Field Connection</span>
            </div>
          </div>
        </div>

        {/* Table Selector Tabs */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 border-b border-zinc-900">
          <span className="text-[10px] font-bold text-zinc-500 uppercase mr-2">FILTER TABLE:</span>
          <button
            type="button"
            onClick={() => setSelectedTableFilter('all')}
            className={`px-3 py-1.5 rounded-none text-xs font-bold uppercase tracking-wider transition-all border ${
              selectedTableFilter === 'all'
                ? 'bg-sky-400/15 border-sky-400 text-sky-400 shadow-[0_0_10px_rgba(56,189,248,0.15)]'
                : 'bg-zinc-950 border-zinc-900 text-zinc-400 hover:border-zinc-800 hover:text-white'
            }`}
          >
            [ ALL MAPPINGS ]
          </button>

          {tableNames.map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => setSelectedTableFilter(name)}
              className={`px-3 py-1.5 rounded-none text-xs font-bold uppercase tracking-wider transition-all border ${
                selectedTableFilter === name
                  ? 'bg-sky-400/15 border-sky-400 text-sky-400 shadow-[0_0_10px_rgba(56,189,248,0.15)]'
                  : 'bg-zinc-950 border-zinc-900 text-zinc-400 hover:border-zinc-800 hover:text-white'
              }`}
            >
              {name}
            </button>
          ))}
        </div>

        {/* Static Column-to-Column SVG Graph Canvas */}
        <div className="w-full overflow-x-auto relative flex justify-center py-6 bg-zinc-950/60 border border-zinc-900">
          {columnRows.length === 0 ? (
            <div className="p-8 text-center text-zinc-500 text-xs font-mono">
              No column mappings registered for this selection.
            </div>
          ) : (
            <svg
              width={svgWidth}
              height={canvasHeight}
              className="overflow-visible"
              style={{ minWidth: `${svgWidth}px` }}
            >
              {/* Static Column Connector Pipes & Nodes */}
              {columnRows.map((row, idx) => {
                const y = 30 + idx * (rowHeight + rowGap) + rowHeight / 2;

                const startX = leftX;
                const endX = rightX;

                // Bezier Curve Static Pipe Path
                const controlDist = (endX - startX) * 0.4;
                const pathString = `M ${startX} ${y} C ${startX + controlDist} ${y}, ${endX - controlDist} ${y}, ${endX} ${y}`;

                const badgeWidth = Math.max(130, row.transformationType.length * 8 + 16);

                return (
                  <g key={row.id}>
                    {/* Static SVG Connector Line */}
                    <path
                      d={pathString}
                      fill="none"
                      stroke="#38bdf8"
                      strokeWidth="1.5"
                      strokeOpacity="0.85"
                    />

                    {/* Source Endpoint Dot */}
                    <circle cx={startX} cy={y} r="3" fill="#38bdf8" />

                    {/* Target Endpoint Dot */}
                    <circle cx={endX} cy={y} r="3" fill="#3b82f6" />

                    {/* Center Static Transformation Badge */}
                    <g transform={`translate(${midX}, ${y})`}>
                      <rect
                        x={-badgeWidth / 2}
                        y="-12"
                        width={badgeWidth}
                        height="24"
                        fill="#000000"
                        stroke="#38bdf8"
                        strokeWidth="1"
                      />
                      <text
                        x="0"
                        y="4"
                        textAnchor="middle"
                        fill="#38bdf8"
                        fontSize="9"
                        fontWeight="bold"
                        className="uppercase tracking-wider"
                      >
                        {row.transformationType}
                      </text>
                    </g>
                  </g>
                );
              })}

              {/* Render Left Column: Source Column Nodes */}
              {columnRows.map((row, idx) => {
                const yTop = 30 + idx * (rowHeight + rowGap);
                const boxW = leftX - 20;

                return (
                  <g key={`src-${row.id}`} transform={`translate(20, ${yTop})`}>
                    {/* Source Column Box */}
                    <rect
                      x="0"
                      y="0"
                      width={boxW}
                      height={rowHeight}
                      fill="#000000"
                      stroke="#27272a"
                      strokeWidth="1"
                    />
                    <rect x="0" y="0" width="4" height={rowHeight} fill="#38bdf8" />

                    <text x="12" y="18" fill="#a1a1aa" fontSize="9" fontWeight="bold" className="uppercase tracking-wider">
                      [{row.sourceIdentifier}] {row.sourceTableName}
                    </text>
                    <text x="12" y="38" fill="#ffffff" fontSize="12" fontWeight="bold">
                      {row.sourceColumnName}
                    </text>
                  </g>
                );
              })}

              {/* Render Right Column: Target Column Nodes */}
              {columnRows.map((row, idx) => {
                const yTop = 30 + idx * (rowHeight + rowGap);
                const boxW = svgWidth - rightX - 20; // 280px

                return (
                  <g key={`tgt-${row.id}`} transform={`translate(${rightX}, ${yTop})`}>
                    {/* Target Column Box */}
                    <rect
                      x="0"
                      y="0"
                      width={boxW}
                      height={rowHeight}
                      fill="#030712"
                      stroke="#3b82f6"
                      strokeWidth="1"
                    />
                    <rect x={boxW - 4} y="0" width="4" height={rowHeight} fill="#3b82f6" />

                    <text x="12" y="18" fill="#60a5fa" fontSize="9" fontWeight="bold" className="uppercase tracking-wider">
                      TARGET: {row.targetTableName}
                    </text>

                    {/* Column Name */}
                    <text x="12" y="38" fill="#ffffff" fontSize="12" fontWeight="bold">
                      {row.targetColumnName}
                    </text>

                    {/* PK Tag */}
                    {row.isPrimaryKey && (
                      <text x="12" y="52" fill="#38bdf8" fontSize="9" fontWeight="bold">
                        [PK]
                      </text>
                    )}

                    {/* Data Type (Right Aligned inside 280px Box) */}
                    <text x={boxW - 16} y={row.isPrimaryKey ? 52 : 38} textAnchor="end" fill="#38bdf8" fontSize="9" fontWeight="bold">
                      {row.targetDataType}
                    </text>
                  </g>
                );
              })}
            </svg>
          )}
        </div>
      </div>
    </div>
  );
};

export default PlanDiagramViewer;
