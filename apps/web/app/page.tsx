import React from 'react';
import Navbar from '../components/landing/Navbar';
import Hero from '../components/landing/Hero';
import PlatformOverview from '../components/landing/PlatformOverview';
import FeaturesGrid from '../components/landing/FeaturesGrid';
import WorkflowSteps from '../components/landing/WorkflowSteps';
import Footer from '../components/landing/Footer';

export const metadata = {
  title: 'Data Migration Platform | High-Performance Schema & ETL Engine',
  description:
    'Automate database schema translation and execute zero-OOM chunked streaming ETL across PostgreSQL, MySQL, MongoDB, and flat files.',
};

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 selection:bg-indigo-600 selection:text-white font-sans">
      <Navbar />
      <Hero />
      <PlatformOverview />
      <FeaturesGrid />
      <WorkflowSteps />
      <Footer />
    </main>
  );
}
