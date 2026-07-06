"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";

const navItems = [
  { id: "command", label: "Command Centre", icon: "dashboard", href: "/" },
  { id: "hermes", label: "Hermes Engine", icon: "auto_awesome", href: "/hermes" },
  { id: "adviser", label: "AI Adviser", icon: "support_agent", href: "/adviser" },
  { id: "synthetic", label: "Synthetic Reality", icon: "science", href: "/synthetic" },
  { id: "whiteboard", label: "Whiteboard", icon: "line_axis", href: "/whiteboard" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden lg:flex fixed left-0 top-0 h-full w-[220px] flex-col bg-aura-surface border-r border-aura-border z-30">
      <div className="h-[64px] flex items-center px-5 border-b border-aura-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-aura-navy flex items-center justify-center">
            <span className="material-symbols-outlined text-white text-[18px]">terminal</span>
          </div>
          <div>
            <div className="font-mono text-sm font-bold text-aura-text">ASSURE</div>
            <div className="font-mono text-[10px] uppercase text-aura-text-subtle">Portfolio Assurance</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 py-4 px-3 flex flex-col gap-1">
        {navItems.map((item) => {
          const active = item.href !== "#" && (item.href === "/" ? pathname === "/" : pathname.startsWith(item.href));
          return (
            <Link
              key={item.id}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2 rounded text-sm font-medium transition-colors",
                active
                  ? "bg-aura-navy text-white"
                  : "text-aura-text-muted hover:bg-aura-surface-low hover:text-aura-text"
              )}
            >
              <span className={clsx("material-symbols-outlined text-[18px]", active && "material-symbols-filled")}>{item.icon}</span>
              <span className="font-mono">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-aura-border">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-aura-emerald" />
          <span className="font-mono text-[10px] uppercase text-aura-text-subtle">System Live</span>
        </div>
      </div>
    </aside>
  );
}
