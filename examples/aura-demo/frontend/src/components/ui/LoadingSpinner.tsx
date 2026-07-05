"use client";

import { clsx } from "clsx";

export function LoadingSpinner({
  size = "md",
  label,
  className,
}: {
  size?: "sm" | "md" | "lg";
  label?: string;
  className?: string;
}) {
  const sizeClass = {
    sm: "text-[16px]",
    md: "text-[20px]",
    lg: "text-[28px]",
  }[size];

  return (
    <span className={clsx("inline-flex items-center gap-2 font-mono text-xs text-aura-text-muted", className)}>
      <span
        className={clsx(
          "material-symbols-outlined animate-spin",
          sizeClass
        )}
        aria-hidden="true"
      >
        progress_activity
      </span>
      {label && <span>{label}</span>}
    </span>
  );
}
