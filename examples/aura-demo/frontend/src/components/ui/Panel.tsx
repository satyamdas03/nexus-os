import { clsx } from "clsx";

export function Panel({
  children,
  className,
  header,
  subheader,
  right,
  "data-tour": dataTour,
  ...rest
}: {
  children: React.ReactNode;
  className?: string;
  header?: React.ReactNode;
  subheader?: React.ReactNode;
  right?: React.ReactNode;
  "data-tour"?: string;
} & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div data-tour={dataTour} {...rest} className={clsx("bg-aura-surface-low border border-aura-border rounded overflow-hidden", className)}>
      {(header || subheader || right) && (
        <div className="px-4 py-3 border-b border-aura-border bg-aura-surface flex items-center justify-between gap-4">
          <div>
            {header && <h3 className="font-mono text-base font-semibold text-aura-text">{header}</h3>}
            {subheader && <p className="font-mono text-xs text-aura-text-subtle mt-0.5">{subheader}</p>}
          </div>
          {right && <div>{right}</div>}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}
