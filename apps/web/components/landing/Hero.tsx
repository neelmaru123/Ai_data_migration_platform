'use client';

import React from 'react';
import SplineHeroBackground from './SplineHeroBackground';
import { ChevronDown } from 'lucide-react';

interface HeroProps {
  sceneUrl?: string;
}

export default function Hero({ sceneUrl }: HeroProps) {
  return (
    <section className="relative w-full bg-black overflow-hidden rounded-none">
      {/* 3D Spline Scene (Fullscreen 100vh, non-interactive, pure black container) */}
      <div className="relative w-full h-screen">
        <SplineHeroBackground sceneUrl={sceneUrl} interactive={false} />

        {/* Scroll Down Indicator - Zero radius, Sky Blue accent */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 flex flex-col items-center gap-2 pointer-events-auto">
          <a
            href="#overview"
            aria-label="Scroll to platform details"
            className="text-zinc-400 hover:text-sky-400 transition-colors animate-bounce p-2 flex flex-col items-center gap-1 text-xs font-mono tracking-widest uppercase rounded-none"
          >
            <span>Scroll To Explore</span>
            <ChevronDown className="w-5 h-5 text-sky-400" />
          </a>
        </div>
      </div>
    </section>
  );
}
