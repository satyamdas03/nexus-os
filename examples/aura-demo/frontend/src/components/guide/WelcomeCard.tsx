"use client";

export function WelcomeCard({
  onStartTour,
  onDismiss,
}: {
  onStartTour: () => void;
  onDismiss: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-aura-navy/30 p-4"
      onClick={onDismiss}
    >
      <div
        className="bg-aura-surface-low border border-aura-border rounded shadow-aura-md max-w-lg w-full p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded bg-aura-navy flex items-center justify-center text-white">
            <span className="material-symbols-outlined">terminal</span>
          </div>
          <h2 className="font-mono text-xl font-bold text-aura-text">Welcome to ASSURE</h2>
        </div>
        <p className="font-mono text-sm text-aura-text-muted mb-4">
          An AI layer on top of portfolio assurance. AI recommends; the
          deterministic rules engine verifies; a human approves every action.
        </p>
        <ol className="font-mono text-sm text-aura-text space-y-2 mb-6 list-decimal pl-4">
          <li>See the whole book — 34,000 portfolios, coloured by mandate status.</li>
          <li>Open a flagged portfolio — read the plain-English explanation of why it's breaching.</li>
          <li>Propose a fix — watch the rules engine verify it before any human approves.</li>
          <li>Run Hermes — let it remediate the entire book at once, safely caged.</li>
        </ol>
        <div className="flex flex-col sm:flex-row gap-3 mb-4">
          <button
            onClick={onStartTour}
            className="flex-1 px-4 py-2 bg-aura-navy text-white rounded font-mono text-sm hover:bg-aura-navy-hover transition-colors"
          >
            Start guided tour
          </button>
          <button
            onClick={onDismiss}
            className="flex-1 px-4 py-2 border border-aura-border text-aura-text rounded font-mono text-sm hover:border-aura-navy transition-colors"
          >
            Explore on my own
          </button>
        </div>
        <p className="font-mono text-[10px] text-aura-text-subtle">
          Everything here runs on synthetic data.
        </p>
      </div>
    </div>
  );
}
