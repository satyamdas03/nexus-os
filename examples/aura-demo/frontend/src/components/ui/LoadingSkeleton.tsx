"use client";

import { ReactNode } from "react";
import { LoadingSpinner } from "./LoadingSpinner";

export function LoadingSkeleton({
  label,
  children,
}: {
  label?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-6" aria-busy="true" aria-live="polite">
      <div className="flex items-center gap-2">
        {label && <LoadingSpinner label={label} />}
      </div>
      {children}
    </div>
  );
}
