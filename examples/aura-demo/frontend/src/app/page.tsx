"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { CommandCentreView } from "@/components/CommandCentreView";
import { AboutPopover } from "@/components/guide/AboutPopover";
import { WelcomeCard } from "@/components/guide/WelcomeCard";
import { useGuideSeen } from "@/components/guide/useGuideSeen";
import { setTourPortfolio, dispatchStartTour } from "@/components/guide/useTour";
import type { PortfolioSummary, TopSafeguard } from "@/lib/types";

export const dynamic = "force-dynamic";

type Summary = { total: number; counts: Record<string, number>; breach_count: number };

export default function Home() {
  const { seen, ready, markSeen } = useGuideSeen();
  const [dismissed, setDismissed] = useState(false);
  const [ps, setPs] = useState<PortfolioSummary[]>([]);
  const [summary, setSummary] = useState<Summary>({ total: 0, counts: {}, breach_count: 0 });
  const [top, setTop] = useState<TopSafeguard | null>(null);
  const [aiNarrative, setAiNarrative] = useState<string | undefined>(undefined);
  const [err, setErr] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.listPortfolios(200, 0),
      api.summary(),
      api.portfoliosTop(200).catch(() => null),
      api.summaryAi().catch(() => undefined),
    ])
      .then(([p, s, t, ai]) => {
        setPs(p);
        setSummary(s);
        setTop(t);
        setAiNarrative(ai?.narrative);
        const pick = p.find((x: PortfolioSummary) => x.status !== "green") ?? p[0];
        if (pick) setTourPortfolio(pick.client_id);
      })
      .catch(() => setErr(true))
      .finally(() => setLoading(false));

    const showGuide = () => setDismissed(false);
    window.addEventListener("assure:show-guide", showGuide);
    return () => window.removeEventListener("assure:show-guide", showGuide);
  }, []);

  const welcomeVisible = ready && !seen && !dismissed;

  return (
    <div className="relative">
      {welcomeVisible && (
        <WelcomeCard
          onDismiss={() => { markSeen(); setDismissed(true); }}
          onStartTour={() => { markSeen(); setDismissed(true); dispatchStartTour(); }}
        />
      )}
      <div className="absolute top-4 right-4 lg:top-6 lg:right-6 z-10">
        <AboutPopover title="About Command Centre">
          <p>The treemap blocks are sized by FUM (funds under management) and coloured by mandate status: green = aligned, orange = drift watch, red = breach.</p>
          <p>The summary bar is grounded in the deterministic rules engine; the AI summary is advisory.</p>
          <p>The Urgent Triage rail ranks portfolios by severity and funds at risk.</p>
        </AboutPopover>
      </div>
      {err ? (
        <div className="p-8 font-mono text-aura-crimson">Backend unreachable. Check backend and retry.</div>
      ) : (
        <CommandCentreView
          initialPortfolios={ps}
          initialSummary={summary}
          aiNarrative={aiNarrative}
          initialTop={top}
          loading={loading}
        />
      )}
    </div>
  );
}
