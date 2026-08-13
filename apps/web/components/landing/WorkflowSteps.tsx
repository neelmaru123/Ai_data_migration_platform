'use client';

import React from 'react';

const steps = [
  {
    number: '01',
    title: 'Connect Databases',
    description: 'Provide connection URIs or upload flat files. Credentials are encrypted securely.',
  },
  {
    number: '02',
    title: 'Schema Profiling',
    description: 'Analyzes tables, foreign keys, and column types to generate an optimal transformation plan.',
  },
  {
    number: '03',
    title: 'Review Plan',
    description: 'Verify and customize column mappings, type casts, and custom rules before execution.',
  },
  {
    number: '04',
    title: 'Execute & Monitor',
    description: 'Stream chunked data deterministically with zero memory spikes and live telemetry dashboards.',
  },
];

export default function WorkflowSteps() {
  return (
    <section id="workflow" className="py-20 bg-slate-950 relative border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Section Header */}
        <div className="max-w-2xl mb-12">
          <div className="text-xs font-mono text-cyan-400 font-bold uppercase tracking-wider mb-2">
            Execution Workflow
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-100 tracking-tight">
            Simple 4-Step Migration Pipeline
          </h2>
        </div>

        {/* Steps Grid - Solid Dark Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          {steps.map((step) => (
            <div
              key={step.number}
              className="p-6 rounded-sm bg-slate-900 border border-slate-800 hover:border-slate-700 transition-colors flex flex-col justify-between"
            >
              <div>
                <div className="font-mono text-2xl font-extrabold text-indigo-400 mb-4">
                  {step.number}
                </div>
                <h3 className="text-base font-bold text-slate-100 mb-2">{step.title}</h3>
                <p className="text-slate-400 text-xs leading-relaxed">{step.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
