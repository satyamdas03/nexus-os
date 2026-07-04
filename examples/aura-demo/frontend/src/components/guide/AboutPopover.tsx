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
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) window.addEventListener("mousedown", handler);
    return () => window.removeEventListener("mousedown", handler);
  }, [open]);

  const triggerElemRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;

    triggerElemRef.current = triggerRef.current;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    // Focus the panel itself so screen readers announce the popover.
    panelRef.current?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        setOpen(false);
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;

      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
      );
      // Include the close button explicitly.
      const closeBtn = panelRef.current.querySelector("button[aria-label='Close']") as HTMLElement | null;
      if (closeBtn && !focusable.includes(closeBtn)) focusable.unshift(closeBtn);
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      // Return focus to the trigger when the popover closes.
      if (previouslyFocused && triggerElemRef.current === previouslyFocused) {
        triggerElemRef.current?.focus();
      }
    };
  }, [open]);

  return (
    <div ref={ref} className={clsx("relative", className)}>
      <button
        ref={triggerRef}
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2 py-1 rounded border border-aura-border text-aura-text-muted hover:text-aura-navy hover:border-aura-navy font-mono text-[11px] transition-colors"
        aria-label="About this view"
        aria-expanded={open}
      >
        <span className="material-symbols-outlined text-[14px]">info</span>
        <span>About this view</span>
      </button>
      {open && (
        <div
          ref={panelRef}
          tabIndex={-1}
          className="absolute right-0 top-full mt-2 w-[320px] z-50 bg-aura-surface-low border border-aura-border rounded shadow-aura-md p-4 outline-none"
          role="dialog"
          aria-modal="true"
          aria-labelledby="about-title"
        >
          <div className="flex items-center justify-between mb-2">
            <h4 id="about-title" className="font-mono text-sm font-semibold text-aura-text">{title}</h4>
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
