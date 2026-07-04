"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { MandateDetail } from "@/lib/types";
import { MandatePanel } from "@/components/MandatePanel";
import { LoadingOverlay } from "@/components/ui/LoadingOverlay";

export default function MandatePage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [detail, setDetail] = useState<MandateDetail | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    api
      .getMandate(id)
      .then(setDetail)
      .catch(() => setErr(true));
  }, [id]);

  if (err) {
    return (
      <div className="p-8 font-mono text-aura-crimson">
        Backend unreachable or mandate not found. Check backend and retry.
      </div>
    );
  }

  if (!detail) {
    return (
      <LoadingOverlay
        label="Loading mandate…"
        subLabel={`Reading the versioned DSL and rule docs for client ${id}.`}
      />
    );
  }

  return (
    <div className="relative p-4 lg:p-6 max-w-[1440px] mx-auto">
      <Link
        href={`/portfolio/${id}`}
        className="inline-flex items-center gap-1.5 text-aura-text-muted hover:text-aura-navy font-mono text-xs mb-4"
      >
        <span className="material-symbols-outlined text-[16px]">arrow_back</span>
        <span className="uppercase tracking-wide">Back to Diagnosis</span>
      </Link>

      <div className="mb-6">
        <p className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider mb-1">
          Entity // {detail.client_id}
        </p>
        <h1 className="font-mono text-2xl font-bold text-aura-text">Mandate View</h1>
        <p className="text-aura-text-muted font-mono text-xs mt-1">
          Deterministic rule definitions and the declarative DSL source.
        </p>
      </div>

      <MandatePanel detail={detail} />
    </div>
  );
}
