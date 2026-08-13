'use client';

import React from 'react';
import Script from 'next/script';

interface SplineHeroBackgroundProps {
  sceneUrl?: string;
  interactive?: boolean;
}

const DEFAULT_SPLINE_URL = 'https://prod.spline.design/E6eFCzHp4BkxYnO7/scene.splinecode';

export default function SplineHeroBackground({
  sceneUrl,
  interactive = false,
}: SplineHeroBackgroundProps) {
  // Ensure valid URL fallback if sceneUrl is empty or string 'undefined'
  const activeUrl =
    sceneUrl && sceneUrl !== 'undefined' ? sceneUrl : DEFAULT_SPLINE_URL;

  return (
    <div className="relative w-full h-screen overflow-hidden select-none bg-black">
      {/* Load official Spline Web Component Viewer Script */}
      <Script
        src="https://unpkg.com/@splinetool/viewer@1.12.98/build/spline-viewer.js"
        type="module"
        strategy="afterInteractive"
      />

      {/* Spline Web Component Element - Interaction disabled to prevent zoom/pan */}
      <div className={`w-full h-full ${interactive ? 'pointer-events-auto' : 'pointer-events-none'}`}>
        {React.createElement('spline-viewer', {
          url: activeUrl,
          'loading-anim-type': 'spinner',
          style: {
            width: '100%',
            height: '100%',
            pointerEvents: interactive ? 'auto' : 'none',
          },
        })}
      </div>
    </div>
  );
}
