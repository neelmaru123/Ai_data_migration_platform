import React from 'react';
import Navbar from '../components/landing/Navbar';
import Hero from '../components/landing/Hero';
import DatabaseFlowDiagram from '../components/landing/DatabaseFlowDiagram';
import FeaturesGrid from '../components/landing/FeaturesGrid';
import WorkflowSteps from '../components/landing/WorkflowSteps';
import Footer from '../components/landing/Footer';
import ScrollLightLine from '../components/landing/ScrollLightLine';

export const metadata = {
  title: 'Migraflow | High-Performance Database Schema & ETL Migration Platform',
  description:
    'Automate database schema translation and execute zero-OOM chunked streaming ETL across PostgreSQL, MySQL, MongoDB, and flat files with Migraflow.',
};

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-black text-slate-100 selection:bg-white selection:text-black font-sans rounded-none relative">
      <Navbar />
      <Hero />

      {/* Content Sections below Hero with Animated Scroll Light Line */}
      <div className="relative">
        <ScrollLightLine />
        <DatabaseFlowDiagram />
        <FeaturesGrid />
        <WorkflowSteps />
      </div>

      {/* Footer rendered outside the scroll light line container */}
      <Footer />
    </main>
  );
}
