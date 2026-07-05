"use client";

import { useState } from "react";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { SecondaryButton } from "@/components/ui/SecondaryButton";
import { api } from "@/lib/api";

interface EvidencePackButtonProps {
  clientId: string;
  variant?: "primary" | "secondary";
}

export function EvidencePackButton({ clientId, variant = "secondary" }: EvidencePackButtonProps) {
  const [loading, setLoading] = useState(false);

  const handleClick = () => {
    setLoading(true);
    try {
      const url = api.evidence.portfolioHtmlUrl(clientId);
      window.open(url, "_blank", "noopener,noreferrer");
    } finally {
      // Brief loading feedback to acknowledge the click; the new tab opens immediately.
      setTimeout(() => setLoading(false), 400);
    }
  };

  const children = (
    <>
      <span className="material-symbols-outlined text-[16px]">description</span>
      Generate Evidence Pack
    </>
  );

  if (variant === "primary") {
    return (
      <PrimaryButton onClick={handleClick} loading={loading} className="whitespace-nowrap">
        {children}
      </PrimaryButton>
    );
  }

  return (
    <SecondaryButton onClick={handleClick} loading={loading} className="whitespace-nowrap">
      {children}
    </SecondaryButton>
  );
}
