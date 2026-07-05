import { clsx } from "clsx";
import type { Status } from "@/lib/types";

const MAP: Record<Status, string> = {
  green: "bg-aura-emerald",
  orange: "bg-aura-ochre",
  red: "bg-aura-crimson",
};

export function StatusDot({ status, className }: { status: Status; className?: string }) {
  return <span className={clsx("w-2 h-2 rounded-full", MAP[status], className)} />;
}
