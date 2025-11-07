'use client';

import React, { useEffect, useState } from 'react';
import UserSelector from './UserSelector';

interface PageRefreshModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRefresh: (feedback: string, provider: string, model: string, isCustomModel: boolean, customModel: string) => void;
  isRefreshing: boolean;
  currentFeedback?: string;
  
  // Current model settings
  provider: string;
  model: string;
  isCustomModel: boolean;
  customModel: string;
}

export default function PageRefreshModal({
  isOpen,
  onClose,
  onRefresh,
  isRefreshing,
  currentFeedback = '',
  provider,
  model,
  isCustomModel,
  customModel,
}: PageRefreshModalProps) {
  // Local state for form values
  const [localFeedback, setLocalFeedback] = useState(currentFeedback);
  const [localProvider, setLocalProvider] = useState(provider);
  const [localModel, setLocalModel] = useState(model);
  const [localIsCustomModel, setLocalIsCustomModel] = useState(isCustomModel);
  const [localCustomModel, setLocalCustomModel] = useState(customModel);

  // Reset local state when modal is opened
  useEffect(() => {
    if (isOpen) {
      setLocalFeedback(currentFeedback);
      setLocalProvider(provider);
      setLocalModel(model);
      setLocalIsCustomModel(isCustomModel);
      setLocalCustomModel(customModel);
    }
  }, [isOpen, currentFeedback, provider, model, isCustomModel, customModel]);

  // Handler for applying refresh
  const handleRefresh = () => {
    onRefresh(
      localFeedback.trim(),
      localProvider,
      localModel,
      localIsCustomModel,
      localCustomModel
    );
  };

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4 text-center bg-black/50">
        <div className="relative transform overflow-hidden rounded-lg bg-[var(--card-bg)] text-left shadow-xl transition-all sm:my-8 sm:max-w-lg sm:w-full">
          {/* Modal header with close button */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-color)]">
            <h3 className="text-lg font-medium text-[var(--accent-primary)] font-serif">
              Refresh Page
            </h3>
            <button
              type="button"
              onClick={onClose}
              className="text-[var(--muted)] hover:text-[var(--foreground)] focus:outline-none transition-colors"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Modal body */}
          <div className="p-6">
            <p className="text-sm text-[var(--muted)] mb-4">
              Add notes about what needs to change, then regenerate the page with those fixes.
            </p>

            {/* Feedback textarea */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-[var(--foreground)] mb-2">
                Feedback / Corrections
              </label>
              <textarea
                className="w-full h-32 text-sm rounded-md border border-[var(--border-color)] bg-[var(--background)] p-3 focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/30 focus:border-[var(--accent-primary)] transition-colors resize-y"
                placeholder="Describe corrections, missing details, or updates you'd like to see..."
                value={localFeedback}
                onChange={(e) => setLocalFeedback(e.target.value)}
                disabled={isRefreshing}
              />
            </div>

            {/* Divider */}
            <div className="my-4 border-t border-[var(--border-color)]/30"></div>

            {/* Model Selector */}
            <div className="mb-2">
              <label className="block text-sm font-medium text-[var(--foreground)] mb-3">
                Model Selection
              </label>
              <UserSelector
                provider={localProvider}
                setProvider={setLocalProvider}
                model={localModel}
                setModel={setLocalModel}
                isCustomModel={localIsCustomModel}
                setIsCustomModel={setLocalIsCustomModel}
                customModel={localCustomModel}
                setCustomModel={setLocalCustomModel}
                showFileFilters={false}
              />
            </div>
          </div>

          {/* Modal footer */}
          <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-[var(--border-color)]">
            <button
              type="button"
              onClick={onClose}
              disabled={isRefreshing}
              className="px-4 py-2 text-sm font-medium rounded-md border border-[var(--border-color)]/50 text-[var(--muted)] bg-transparent hover:bg-[var(--background)] hover:text-[var(--foreground)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="px-4 py-2 text-sm font-medium rounded-md border border-transparent bg-[var(--accent-primary)]/90 text-white hover:bg-[var(--accent-primary)] transition-colors disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isRefreshing ? (
                <>
                  <span className="h-3 w-3 rounded-full border-2 border-white/40 border-t-transparent animate-spin"></span>
                  Refreshing…
                </>
              ) : (
                'Refresh Page'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

