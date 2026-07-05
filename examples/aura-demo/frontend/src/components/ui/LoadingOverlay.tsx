"use client";

import { LoadingSpinner } from "./LoadingSpinner";

export function LoadingOverlay({
  label = "Loading...",
  subLabel,
  className,
}: {
  label?: string;
  subLabel?: string;
  className?: string;
}) {
  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-aura-navy/30 backdrop-blur-sm p-4"
      aria-live="polite"
      aria-busy="true"
    >
      <div
        className={`bg-aura-surface-low border border-aura-border rounded shadow-aura-md max-w-md w-full p-6 ${className ?? ""}`}
      >
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded bg-aura-navy flex items-center justify-center text-white shrink-0">
            <span className="material-symbols-outlined animate-spin">progress_activity</span>
          </div>
          <div>
            <h3 className="font-mono text-sm font-semibold text-aura-text mb-1">{label}</h3>
            {subLabel && (
              <p className="font-mono text-xs text-aura-text-muted leading-relaxed">{subLabel}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
