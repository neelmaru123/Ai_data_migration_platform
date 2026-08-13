'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { ArrowRight, Menu, X } from 'lucide-react';

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-200 ${
        scrolled
          ? 'bg-slate-950 border-b border-slate-800 py-3.5 shadow-xl'
          : 'bg-slate-950/80 border-b border-slate-900 py-5'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-sm bg-indigo-950 border border-indigo-600/50 flex items-center justify-center text-indigo-300 font-extrabold text-sm tracking-widest group-hover:border-indigo-500 transition-colors">
              N
            </div>
            <span className="font-bold text-base tracking-tight text-slate-100 uppercase">
              Nexus<span className="text-indigo-400">Data</span>
            </span>
          </Link>

          {/* Nav Links */}
          <nav className="hidden md:flex items-center gap-8 text-xs font-semibold text-slate-300 tracking-wider uppercase">
            <a href="#overview" className="hover:text-white transition-colors">
              Architecture
            </a>
            <a href="#features" className="hover:text-white transition-colors">
              Capabilities
            </a>
            <a href="#workflow" className="hover:text-white transition-colors">
              Workflow
            </a>
          </nav>

          {/* Action CTAs */}
          <div className="hidden md:flex items-center gap-3">
            <Link
              href="/login"
              className="text-xs font-semibold uppercase tracking-wider text-slate-300 hover:text-white px-3.5 py-2 rounded-sm border border-slate-800 hover:border-slate-700 bg-slate-900 transition-all"
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="text-xs font-semibold uppercase tracking-wider px-4 py-2 rounded-sm bg-indigo-600 hover:bg-indigo-500 text-white transition-colors flex items-center gap-1.5 shadow-md shadow-indigo-950"
            >
              <span>Get Started</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {/* Mobile Menu Toggle */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden text-slate-400 hover:text-white p-2"
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden mt-3 p-4 rounded-sm bg-slate-900 border border-slate-800 flex flex-col gap-3">
            <a
              href="#overview"
              onClick={() => setMobileMenuOpen(false)}
              className="text-slate-300 hover:text-white py-1 text-xs font-semibold uppercase"
            >
              Architecture
            </a>
            <a
              href="#features"
              onClick={() => setMobileMenuOpen(false)}
              className="text-slate-300 hover:text-white py-1 text-xs font-semibold uppercase"
            >
              Capabilities
            </a>
            <a
              href="#workflow"
              onClick={() => setMobileMenuOpen(false)}
              className="text-slate-300 hover:text-white py-1 text-xs font-semibold uppercase"
            >
              Workflow
            </a>
            <div className="pt-2 border-t border-slate-800 flex flex-col gap-2">
              <Link
                href="/login"
                onClick={() => setMobileMenuOpen(false)}
                className="w-full text-center py-2 text-xs font-semibold uppercase text-slate-300 bg-slate-800"
              >
                Sign In
              </Link>
              <Link
                href="/register"
                onClick={() => setMobileMenuOpen(false)}
                className="w-full text-center py-2 rounded-sm bg-indigo-600 text-white text-xs font-semibold uppercase"
              >
                Get Started
              </Link>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
