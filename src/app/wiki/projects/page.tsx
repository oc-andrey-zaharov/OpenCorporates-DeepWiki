'use client';

import React from 'react';
import Link from 'next/link';
import { FaWikipediaW, FaGithub } from 'react-icons/fa';
import ThemeToggle from '@/components/theme-toggle';
import ProcessedProjects from '@/components/ProcessedProjects';

export default function WikiProjectsPage() {

  return (
    <div className="h-screen paper-texture p-4 md:p-8 flex flex-col">
      <header className="max-w-6xl mx-auto mb-6 h-fit w-full">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-[var(--card-bg)] rounded-lg shadow-custom border border-[var(--border-color)] p-4">
          <div className="flex items-center gap-4">
            <div className="bg-[var(--accent-primary)] p-2 rounded-lg">
              <FaWikipediaW className="text-2xl text-white" />
            </div>
            <div>
              <h1 className="text-xl md:text-2xl font-bold text-[var(--accent-primary)]">Processed Wiki Projects</h1>
              <p className="text-xs text-[var(--muted)] mt-0.5">Browse Existing Projects</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="px-4 py-2 rounded-lg border border-[var(--border-color)] text-sm text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10 transition-colors"
            >
              Back to Home
            </Link>
            <a
              href="https://github.com/oc-andrey-zaharov/OpenCorporates-DeepWiki"
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-2 rounded-lg border border-[var(--border-color)] text-sm text-[var(--muted)] hover:text-[var(--accent-primary)] hover:border-[var(--accent-primary)] transition-colors flex items-center gap-2"
            >
              <FaGithub className="h-4 w-4" />
              <span>GitHub</span>
            </a>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-6xl mx-auto w-full overflow-y-auto">
        <div className="min-h-full flex flex-col gap-8 p-6 md:p-8 bg-[var(--card-bg)] rounded-lg shadow-custom border border-[var(--border-color)]">
          <section className="max-w-3xl mx-auto text-center space-y-3">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] text-xs font-medium">
              <span>Wiki Projects</span>
            </div>
            <h2 className="text-3xl font-serif text-[var(--foreground)]">Existing Projects</h2>
            <p className="text-sm text-[var(--muted)] leading-relaxed">
              Browse Existing Projects
            </p>
          </section>

          <ProcessedProjects
            showHeader={false}
            className="w-full"
          />
        </div>
      </main>

      <footer className="max-w-6xl mx-auto mt-8 flex flex-col gap-4 w-full">
        <div className="flex flex-col sm:flex-row justify-between items-center gap-4 bg-[var(--card-bg)] rounded-lg p-4 border border-[var(--border-color)] shadow-custom">
          <p className="text-[var(--muted)] text-sm font-serif">
            OpenCorporates DeepWiki - AI-powered documentation for code repositories
          </p>
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="text-[var(--muted)] hover:text-[var(--accent-primary)] transition-colors text-sm"
            >
              Back to Home
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </footer>
    </div>
  );
}
