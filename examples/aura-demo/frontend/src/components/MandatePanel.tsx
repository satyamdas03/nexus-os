"use client";

import type { MandateDetail, RuleDoc } from "@/lib/types";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { useState } from "react";

function StatusBadge({ enabled }: { enabled: boolean }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider ${
        enabled
          ? "bg-aura-emerald/10 text-aura-emerald border border-aura-emerald/30"
          : "bg-aura-slate/10 text-aura-text-muted border border-aura-border"
      }`}
    >
      {enabled ? "Enabled" : "Disabled"}
    </span>
  );
}

function SeverityBadge({ severity }: { severity: RuleDoc["severity"] }) {
  if (!severity) return null;
  const color =
    severity === "hard breach"
      ? "text-aura-crimson bg-aura-crimson/10 border-aura-crimson/30"
      : severity === "soft breach"
      ? "text-aura-ochre bg-aura-ochre/10 border-aura-ochre/30"
      : "text-aura-navy bg-aura-navy/10 border-aura-navy/30";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider border ${color}`}
    >
      {severity}
    </span>
  );
}

function RuleCard({ rule, idx }: { rule: RuleDoc; idx: number }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="p-4 rounded-lg bg-aura-surface border border-aura-border">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="font-mono text-[10px] text-aura-text-subtle uppercase tracking-wider">
              {idx + 1}. {rule.type}
            </span>
            <StatusBadge enabled={rule.enabled} />
            <SeverityBadge severity={rule.severity} />
          </div>
          <h3 className="font-mono text-sm font-semibold text-aura-text">{rule.title}</h3>
          <p className="text-xs text-aura-text-muted mt-0.5">{rule.summary}</p>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-aura-text-muted hover:text-aura-navy font-mono text-xs flex items-center gap-1"
        >
          <span>{expanded ? "Less" : "Details"}</span>
          <span className="material-symbols-outlined text-[16px]">
            {expanded ? "expand_less" : "expand_more"}
          </span>
        </button>
      </div>
      <p className="text-sm text-aura-text mt-2">{rule.description}</p>
      {expanded && (
        <div className="mt-3 p-2 rounded bg-aura-bg font-mono text-[10px] text-aura-text-muted overflow-x-auto">
          <pre>{JSON.stringify(rule.parameters, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export function MandatePanel({ detail }: { detail: MandateDetail }) {
  const [showDsl, setShowDsl] = useState(false);
  const docs = detail.docs;

  return (
    <div className="space-y-6">
      <div className="p-4 rounded-lg bg-aura-surface border border-aura-border">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-3">
          <div>
            <p className="font-mono text-[10px] uppercase text-aura-text-subtle tracking-wider">Mandate</p>
            <h2 className="font-mono text-lg font-bold text-aura-text">{docs.name || "Unnamed mandate"}</h2>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] px-2 py-1 rounded bg-aura-bg border border-aura-border text-aura-text-muted">
              v{docs.version}
            </span>
            <span className="font-mono text-[10px] px-2 py-1 rounded bg-aura-bg border border-aura-border text-aura-text-muted">
              {docs.enabled_rule_count}/{docs.rule_count} rules enabled
            </span>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs font-mono text-aura-text-muted">
          <div>
            <span className="text-aura-text-subtle">Source:</span> {detail.source_path || "unknown"}
          </div>
          <div>
            <span className="text-aura-text-subtle">Hash:</span> {detail.spec_hash.slice(0, 16)}…
          </div>
          <div>
            <span className="text-aura-text-subtle">Created:</span> {detail.created_ts}
          </div>
          <div>
            <span className="text-aura-text-subtle">Client:</span> {detail.client_id}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => setShowDsl(false)}
          className={`font-mono text-xs uppercase tracking-wider pb-1 border-b-2 ${
            !showDsl ? "border-aura-navy text-aura-navy" : "border-transparent text-aura-text-muted"
          }`}
        >
          Rule Docs
        </button>
        <button
          onClick={() => setShowDsl(true)}
          className={`font-mono text-xs uppercase tracking-wider pb-1 border-b-2 ${
            showDsl ? "border-aura-navy text-aura-navy" : "border-transparent text-aura-text-muted"
          }`}
        >
          Raw DSL
        </button>
      </div>

      {showDsl ? (
        <section>
          <SectionHeader label="Declarative DSL" title="Regulator-reviewable mandate source" />
          <div className="p-3 rounded-lg bg-aura-surface border border-aura-border overflow-x-auto">
            <pre className="font-mono text-xs text-aura-text leading-relaxed whitespace-pre">{detail.dsl}</pre>
          </div>
        </section>
      ) : (
        <section className="space-y-3">
          <SectionHeader label="Rules" title={`${docs.rule_count} mandate rules`} />
          {docs.rules.map((rule, idx) => (
            <RuleCard key={`${rule.type}-${idx}`} rule={rule} idx={idx} />
          ))}
        </section>
      )}
    </div>
  );
}
