import { clsx } from "clsx";

export function SecondaryButton({
  children,
  onClick,
  disabled,
  loading,
  className,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
}) {
  const isBusy = disabled || loading;
  return (
    <button
      onClick={onClick}
      disabled={isBusy}
      aria-busy={loading ? "true" : undefined}
      className={clsx(
        "px-4 py-2 rounded border border-aura-border text-aura-navy font-mono text-sm font-medium",
        "hover:bg-aura-surface disabled:opacity-50 disabled:cursor-not-allowed transition-colors",
        "inline-flex items-center justify-center gap-2",
        className
      )}
    >
      {loading && (
        <span className="material-symbols-outlined text-[16px] animate-spin">progress_activity</span>
      )}
      {children}
    </button>
  );
}
