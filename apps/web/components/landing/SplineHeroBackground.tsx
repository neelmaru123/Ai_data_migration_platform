'use client';

import React, { useState, useEffect } from 'react';
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
  const [hasError, setHasError] = useState(false);

  const activeUrl =
    sceneUrl && sceneUrl !== 'undefined' ? sceneUrl : DEFAULT_SPLINE_URL;

  const isIframeUrl = activeUrl.includes('my.spline.design');

  // Intercept spline-viewer async fetch errors & unhandled rejections
  useEffect(() => {
    const handleGlobalError = (event: ErrorEvent) => {
      if (
        event.message?.includes('Failed to fetch') ||
        event.filename?.includes('spline-viewer')
      ) {
        setHasError(true);
      }
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const reasonStr = String(event.reason?.message || event.reason || '');
      if (reasonStr.includes('Failed to fetch') || reasonStr.includes('spline')) {
        event.preventDefault(); // Intercepts error overlay in Next.js dev mode
        setHasError(true);
      }
    };

    window.addEventListener('error', handleGlobalError);
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    return () => {
      window.removeEventListener('error', handleGlobalError);
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, []);

  return (
    <div className="relative w-full h-screen overflow-hidden select-none bg-black">
      {/* Load official Spline Web Component Viewer Script when using .splinecode URLs */}
      {!isIframeUrl && (
        <Script
          src="https://unpkg.com/@splinetool/viewer@1.12.98/build/spline-viewer.js"
          type="module"
          strategy="afterInteractive"
          onError={() => setHasError(true)}
        />
      )}

      {!hasError ? (
        <div className={`w-full h-full ${interactive ? 'pointer-events-auto' : 'pointer-events-none'}`}>
          {isIframeUrl ? (
            <iframe
              src={activeUrl}
              className="w-full h-full border-0"
              style={{ pointerEvents: interactive ? 'auto' : 'none' }}
              title="Spline 3D Auth Scene"
            />
          ) : (
            React.createElement('spline-viewer', {
              url: activeUrl,
              'loading-anim-type': 'spinner',
              style: {
                width: '100%',
                height: '100%',
                pointerEvents: interactive ? 'auto' : 'none',
              },
            })
          )}
        </div>
      ) : (
        /* Clean Black Fallback graphic */
        <div className="w-full h-full flex flex-col items-center justify-center p-8 text-center bg-black">
          <div className="w-16 h-16 rounded-sm bg-neutral-900 border border-neutral-800 flex items-center justify-center text-neutral-200 font-mono font-bold text-xl mb-4">
            ETL
          </div>
          <h3 className="text-lg font-bold text-slate-100 mb-2">Migraflow Engine</h3>
          <p className="text-xs font-mono text-slate-400 max-w-sm">
            High-Performance Database Schema & Streaming Engine
          </p>
        </div>
      )}
    </div>
  );
}
