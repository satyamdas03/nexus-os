"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import { Sidebar } from "@/components/ui/Sidebar";
import { useGuideSeen } from "@/components/guide/useGuideSeen";
import { GuidedTour } from "@/components/guide/GuidedTour";
import { dispatchStartTour } from "@/components/guide/useTour";

function ShowGuideButton() {
  const { reset } = useGuideSeen();
  return (
    <button
      onClick={() => {
        reset();
        dispatchStartTour();
      }}
      className="p-2 rounded border border-aura-border text-aura-text-muted hover:text-aura-navy hover:border-aura-navy transition-colors"
      aria-label="Show guide"
      title="Show guide"
    >
      <span className="material-symbols-outlined text-[18px]">help</span>
    </button>
  );
}

const mobileTabs = [
  { id: "command", label: "Command", icon: "dashboard", href: "/" },
  { id: "hermes", label: "Hermes", icon: "auto_awesome", href: "/hermes" },
];

// NOTE: "Diagnosis" and "Workbench" are reached from inside the Command Centre / portfolio flow,
// not as top-level nav items. The top-level rail only hosts global destinations.

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const isHome = pathname === "/";

  return (
    <div className="min-h-screen bg-aura-background">
      <Sidebar />

      <header className="fixed top-0 left-0 lg:left-[220px] right-0 h-[64px] bg-aura-surface border-b border-aura-border flex items-center justify-between px-4 lg:px-6 z-20">
        <div className="flex items-center gap-3">
          <button
            className="lg:hidden p-2 -ml-2 rounded hover:bg-aura-surface-low text-aura-text"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open navigation"
          >
            <span className="material-symbols-outlined">menu</span>
          </button>
          <div className="hidden lg:block font-mono text-[10px] uppercase text-aura-text-subtle">
            ASSURE / Portfolio Assurance Platform
          </div>
        </div>
        <div className="flex items-center gap-3">
          <ShowGuideButton />
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded bg-aura-surface-low border border-aura-border">
            <span className="w-2 h-2 rounded-full bg-aura-emerald" />
            <span className="font-mono text-[10px] uppercase text-aura-navy">Live</span>
          </div>
        </div>
      </header>

      {drawerOpen && (
        <div className="lg:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-aura-navy/30" onClick={() => setDrawerOpen(false)} />
          <aside className="absolute left-0 top-0 h-full w-[220px] bg-aura-surface border-r border-aura-border flex flex-col">
            <div className="h-[64px] flex items-center px-5 border-b border-aura-border justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded bg-aura-navy flex items-center justify-center">
                  <span className="material-symbols-outlined text-white text-[18px]">terminal</span>
                </div>
                <span className="font-mono text-sm font-bold text-aura-text">ASSURE</span>
              </div>
              <button onClick={() => setDrawerOpen(false)} aria-label="Close navigation">
                <span className="material-symbols-outlined text-aura-text">close</span>
              </button>
            </div>
            <nav className="flex-1 py-4 px-3 flex flex-col gap-1">
              {mobileTabs.map((tab) => {
                const active = tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);
                return (
                  <Link
                    key={tab.id}
                    href={tab.href}
                    onClick={() => setDrawerOpen(false)}
                    className={clsx(
                      "flex items-center gap-3 px-3 py-2 rounded text-sm font-medium",
                      active ? "bg-aura-navy text-white" : "text-aura-text-muted hover:bg-aura-surface-low"
                    )}
                  >
                    <span className="material-symbols-outlined text-[18px]">{tab.icon}</span>
                    <span className="font-mono">{tab.label}</span>
                  </Link>
                );
              })}
            </nav>
          </aside>
        </div>
      )}

      <GuidedTour />
      <main className="pt-[64px] lg:pl-[220px] min-h-screen bg-aura-background">
        <div className="pb-24">{children}</div>
      </main>

      {isHome && (
        <nav className="lg:hidden fixed bottom-0 left-0 right-0 bg-aura-surface border-t border-aura-border z-40 flex justify-around items-center h-16">
          {mobileTabs.map((tab) => {
            const active = tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);
            return (
              <Link
                key={tab.id}
                href={tab.href}
                className={clsx(
                  "flex flex-col items-center justify-center gap-0.5 w-full h-full text-[11px] font-medium",
                  active ? "text-aura-navy" : "text-aura-text-muted"
                )}
              >
                <span className={clsx("material-symbols-outlined text-[22px]", active && "material-symbols-filled")}>{tab.icon}</span>
                <span className="font-mono uppercase">{tab.label}</span>
              </Link>
            );
          })}
        </nav>
      )}
    </div>
  );
}
