"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AdviserWhiteboard } from "@/lib/types";
import { AdviserCanvas } from "@/components/adviser/AdviserCanvas";
import { AdviserChat } from "@/components/adviser/AdviserChat";
import { AdviserControls } from "@/components/adviser/AdviserControls";

export default function AdviserPage() {
  const [portfolios, setPortfolios] = useState<{ client_id: string; client_name: string }[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [whiteboard, setWhiteboard] = useState<AdviserWhiteboard | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.listPortfolios(100, 0).then((ps) => {
      setPortfolios(ps.map((p) => ({ client_id: p.client_id, client_name: p.client_name })));
    });
  }, []);

  useEffect(() => {
    if (!selected) {
      setWhiteboard(null);
      return;
    }
    setLoading(true);
    api.adviser
      .whiteboard(selected)
      .then(setWhiteboard)
      .catch(() => setWhiteboard(null))
      .finally(() => setLoading(false));
  }, [selected]);

  return (
    <div className="p-4 lg:p-6 max-w-[1440px] mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-6">
        <div>
          <h1 className="font-mono text-2xl font-bold text-aura-text">AI Investment Adviser</h1>
          <p className="font-mono text-xs text-aura-text-muted">Grounded, advisory-only explanations with optional voice session.</p>
        </div>
        <select
          value={selected ?? ""}
          onChange={(e) => setSelected(e.target.value || null)}
          className="px-3 py-2 rounded border border-aura-border bg-aura-background text-sm"
        >
          <option value="">Select portfolio</option>
          {portfolios.map((p) => (
            <option key={p.client_id} value={p.client_id}>
              {p.client_name} ({p.client_id})
            </option>
          ))}
        </select>
      </div>

      {loading && <p className="font-mono text-xs text-aura-text-muted">Loading whiteboard…</p>}

      {whiteboard && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-6">
            <AdviserCanvas whiteboard={whiteboard} />
            <AdviserControls clientId={whiteboard.client_id} />
          </div>
          <div>
            <AdviserChat clientId={whiteboard.client_id} />
          </div>
        </div>
      )}
    </div>
  );
}
