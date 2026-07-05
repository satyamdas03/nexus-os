export function SectionHeader({ label, title }: { label?: string; title: string }) {
  return (
    <div className="mb-3">
      {label && <p className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider mb-1">{label}</p>}
      <h2 className="font-mono text-lg font-semibold text-aura-text">{title}</h2>
    </div>
  );
}
