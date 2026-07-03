"use client";

import { useEffect, useRef, useState } from "react";
import { clsx } from "clsx";

export function AboutPopover({
  title,
  children,
  className,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) window.addEventListener("mousedown", handler);
    return () => window.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div ref={ref} className={clsx("relative", className)}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2 py-1 rounded border border-aura-border text-aura-text-muted hover:text-aura-navy hover:border-aura-navy font-mono text-[11px] transition-colors"
        aria-label="About this view"
      >
        <span className="material-symbols-outlined text-[14px]">info</span>
        <span>About this view</span>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-2 w-[320px] z-50 bg-aura-surface-low border border-aura-border rounded shadow-aura-md p-4">
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-mono text-sm font-semibold text-aura-text">{title}</h4>
            <button
              onClick={() => setOpen(false)}
              className="text-aura-text-muted hover:text-aura-navy"
              aria-label="Close"
            >
              <span className="material-symbols-outlined text-[18px]">close</span>
            </button>
          </div>
          <div className="font-mono text-xs text-aura-text-muted space-y-2 leading-relaxed">
            {children}
          </div>
        </div>
      )}
    </div>
  );
}
