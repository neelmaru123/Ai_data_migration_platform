'use client';

import React, { useEffect, useState, useRef } from 'react';

export default function ScrollLightLine() {
  const [scrollProgress, setScrollProgress] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleScroll = () => {
      if (!containerRef.current) return;

      const parent = containerRef.current.parentElement;
      if (!parent) return;

      const rect = parent.getBoundingClientRect();
      const parentTopInPage = rect.top + window.scrollY;
      const parentHeight = rect.height;
      const viewportHeight = window.innerHeight;

      // Account for Sticky Navbar height (~80px offset) so activation is instant below navbar
      const navbarOffset = 80;
      const scrolledInParent = window.scrollY - parentTopInPage + navbarOffset + viewportHeight * 0.35;
      const maxScrollInParent = parentHeight - viewportHeight * 0.4;

      if (scrolledInParent <= 0) {
        setScrollProgress(0);
      } else if (maxScrollInParent > 0) {
        const progress = (scrolledInParent / maxScrollInParent) * 100;
        setScrollProgress(Math.min(100, Math.max(0, progress)));
      } else {
        setScrollProgress(100);
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Section Branch Percentages aligned precisely with section card centers
  const branchSections = [
    { topPercent: 25, label: 'Topology Diagram Nodes' },
    { topPercent: 55, label: 'Capabilities Cards' },
    { topPercent: 86, label: 'Workflow 4-Step Cards (Center)' },
  ];

  return (
    <div
      ref={containerRef}
      className="absolute left-4 sm:left-8 top-0 bottom-0 w-0.5 z-40 pointer-events-none hidden md:block"
    >
      {/* Background Track Line starting at Overview section and stopping before Footer */}
      <div className="absolute inset-0 bg-white/10" />

      {/* Animated Glowing Light Beam Line */}
      <div
        className="absolute top-0 left-0 w-full bg-gradient-to-b from-sky-400 via-sky-300 to-sky-500 shadow-[0_0_12px_#38bdf8] transition-all duration-75 ease-out"
        style={{ height: `${scrollProgress}%` }}
      >
        {/* Leading Glowing Light Dot */}
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 w-3 h-3 rounded-full bg-sky-400 shadow-[0_0_16px_4px_#38bdf8] animate-pulse" />
      </div>

      {/* Horizontal Branch Lines connecting to Landing Page Sections */}
      {branchSections.map((branch, index) => {
        const isActive = scrollProgress >= branch.topPercent;

        return (
          <div
            key={index}
            className="absolute left-0 flex items-center transition-all duration-300"
            style={{ top: `${branch.topPercent}%` }}
          >
            {/* Horizontal Glowing Branch Laser */}
            <div
              className={`h-0.5 transition-all duration-500 ${
                isActive
                  ? 'w-16 sm:w-24 bg-gradient-to-r from-sky-400 via-sky-300 to-transparent shadow-[0_0_10px_#38bdf8]'
                  : 'w-8 sm:w-12 bg-white/15'
              }`}
            />
            {/* Branch Endpoint Node Dot */}
            <div
              className={`w-2.5 h-2.5 rounded-full transition-all duration-300 -ml-1 ${
                isActive
                  ? 'bg-sky-400 shadow-[0_0_12px_3px_#38bdf8] animate-ping'
                  : 'bg-zinc-700 border border-zinc-600'
              }`}
            />
          </div>
        );
      })}
    </div>
  );
}
