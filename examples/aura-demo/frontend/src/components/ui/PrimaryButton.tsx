import { clsx } from "clsx";

export function PrimaryButton({
  children,
  onClick,
  disabled,
  loading,
  type = "button",
  className,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  type?: "button" | "submit";
  className?: string;
}) {
  const isBusy = disabled || loading;
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={isBusy}
      aria-busy={loading ? "true" : undefined}
      className={clsx(
        "px-4 py-2 rounded bg-aura-navy text-white font-mono text-sm font-medium",
        "hover:bg-aura-navy-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors",
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
