import { clsx } from "clsx";
import type { Status } from "@/lib/types";
import { StatusDot } from "@/components/ui/StatusDot";

const LABEL: Record<Status, string> = {
  green: "ALIGNED",
  orange: "ATTENTION",
  red: "BREACH",
};

const STYLE: Record<Status, string> = {
  green: "bg-aura-emerald-soft border-aura-emerald text-aura-emerald",
  orange: "bg-aura-ochre-soft border-aura-ochre text-aura-ochre",
  red: "bg-aura-crimson-soft border-aura-crimson text-aura-crimson",
};

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider border font-mono",
        STYLE[status]
      )}
    >
      <StatusDot status={status} />
      {LABEL[status]}
    </span>
  );
}
