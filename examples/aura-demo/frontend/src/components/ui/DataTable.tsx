import { clsx } from "clsx";

export function DataTable({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("overflow-x-auto", className)}>
      <table className="w-full text-left border-collapse">{children}</table>
    </div>
  );
}

export function DataTableHead({ children }: { children: React.ReactNode }) {
  return <thead className="bg-aura-surface border-b border-aura-border">{children}</thead>;
}

export function DataTableBody({ children }: { children: React.ReactNode }) {
  return <tbody className="divide-y divide-aura-border">{children}</tbody>;
}

export function DataTableRow({
  children,
  highlighted,
}: {
  children: React.ReactNode;
  highlighted?: boolean;
}) {
  return (
    <tr
      className={clsx(
        "hover:bg-aura-surface transition-colors",
        highlighted ? "bg-aura-crimson-soft" : "even:bg-aura-surface-low"
      )}
    >
      {children}
    </tr>
  );
}

export function DataTableCell({
  children,
  align = "left",
  className,
}: {
  children: React.ReactNode;
  align?: "left" | "right" | "center";
  className?: string;
}) {
  return (
    <td
      className={clsx(
        "px-3 py-3 font-mono text-sm text-aura-text",
        align === "right" && "text-right",
        align === "center" && "text-center",
        className
      )}
    >
      {children}
    </td>
  );
}

export function DataTableHeader({
  children,
  align = "left",
}: {
  children: React.ReactNode;
  align?: "left" | "right" | "center";
}) {
  return (
    <th
      className={clsx(
        "px-3 py-2.5 font-mono text-[10px] uppercase tracking-wider text-aura-text-subtle font-semibold",
        align === "right" && "text-right",
        align === "center" && "text-center"
      )}
    >
      {children}
    </th>
  );
}
