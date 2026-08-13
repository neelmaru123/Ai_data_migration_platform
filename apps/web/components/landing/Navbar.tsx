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

  const handleNavClick = (e: React.MouseEvent<HTMLAnchorElement>, targetId: string) => {
    e.preventDefault();
    setMobileMenuOpen(false);
    const element = document.getElementById(targetId);
    if (element) {
      const navbarHeight = 80;
      const elementPosition = element.getBoundingClientRect().top + window.scrollY;
      window.scrollTo({
        top: elementPosition - navbarHeight,
        behavior: 'smooth',
      });
    }
  };

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 rounded-none ${
        scrolled
          ? 'bg-black/70 backdrop-blur-xl border-b border-sky-400/20 py-3.5 shadow-2xl'
          : 'bg-black/40 backdrop-blur-md border-b border-sky-400/10 py-5'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-none bg-sky-950/80 backdrop-blur-xl border border-sky-400/40 flex items-center justify-center text-sky-400 font-extrabold text-sm tracking-widest group-hover:border-sky-300 transition-colors">
              M
            </div>
            <span className="font-bold text-base tracking-tight text-white uppercase">
              Migra<span className="text-sky-400">flow</span>
            </span>
          </Link>

          {/* Nav Links with Smooth Scroll Offset */}
          <nav className="hidden md:flex items-center gap-8 text-xs font-semibold text-zinc-300 tracking-wider uppercase">
            <a
              href="#overview"
              onClick={(e) => handleNavClick(e, 'overview')}
              className="hover:text-sky-400 transition-colors"
            >
              Architecture
            </a>
            <a
              href="#features"
              onClick={(e) => handleNavClick(e, 'features')}
              className="hover:text-sky-400 transition-colors"
            >
              Capabilities
            </a>
            <a
              href="#workflow"
              onClick={(e) => handleNavClick(e, 'workflow')}
              className="hover:text-sky-400 transition-colors"
            >
              Workflow
            </a>
          </nav>

          {/* Action CTAs */}
          <div className="hidden md:flex items-center gap-3">
            <Link
              href="/login"
              className="text-xs font-semibold uppercase tracking-wider text-sky-200 hover:text-white px-4 py-2 rounded-none border border-sky-400/20 hover:border-sky-400/50 bg-sky-400/10 backdrop-blur-xl transition-all"
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="text-xs font-semibold uppercase tracking-wider px-4 py-2 rounded-none bg-sky-400 hover:bg-sky-300 text-black font-bold transition-colors flex items-center gap-1.5 shadow-lg shadow-sky-950/50"
            >
              <span>Get Started</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {/* Mobile Menu Toggle */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden text-zinc-400 hover:text-sky-400 p-2 rounded-none"
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden mt-3 p-4 rounded-none bg-black/90 backdrop-blur-2xl border border-sky-400/20 flex flex-col gap-3">
            <a
              href="#overview"
              onClick={(e) => handleNavClick(e, 'overview')}
              className="text-zinc-300 hover:text-sky-400 py-1 text-xs font-semibold uppercase"
            >
              Architecture
            </a>
            <a
              href="#features"
              onClick={(e) => handleNavClick(e, 'features')}
              className="text-zinc-300 hover:text-sky-400 py-1 text-xs font-semibold uppercase"
            >
              Capabilities
            </a>
            <a
              href="#workflow"
              onClick={(e) => handleNavClick(e, 'workflow')}
              className="text-zinc-300 hover:text-sky-400 py-1 text-xs font-semibold uppercase"
            >
              Workflow
            </a>
            <div className="pt-2 border-t border-sky-400/10 flex flex-col gap-2">
              <Link
                href="/login"
                onClick={() => setMobileMenuOpen(false)}
                className="w-full text-center py-2 text-xs font-semibold uppercase text-sky-200 bg-sky-400/10 backdrop-blur-xl rounded-none border border-sky-400/20"
              >
                Sign In
              </Link>
              <Link
                href="/register"
                onClick={() => setMobileMenuOpen(false)}
                className="w-full text-center py-2 rounded-none bg-sky-400 text-black font-bold text-xs uppercase"
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
