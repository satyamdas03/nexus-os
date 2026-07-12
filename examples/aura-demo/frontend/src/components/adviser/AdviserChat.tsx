"use client";

import { useState } from "react";
import { api } from "@/lib/api";

type Message = { role: "user" | "assistant"; text: string };

export function AdviserChat({ clientId, disabled }: { clientId: string; disabled?: boolean }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  const send = async () => {
    if (!input.trim() || disabled) return;
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text: input }]);
    try {
      const res = await api.adviser.chat(clientId, input);
      setMessages((m) => [...m, { role: "assistant", text: res.answer }]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: "Sorry, the adviser engine is unreachable." },
      ]);
    }
    setInput("");
    setBusy(false);
  };

  return (
    <div className="bg-aura-surface border border-aura-border rounded p-4 space-y-3">
      <div className="h-48 overflow-y-auto space-y-2 bg-aura-surface-low rounded p-3 border border-aura-border">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`text-sm font-mono ${m.role === "user" ? "text-aura-navy" : "text-aura-text"}`}
          >
            <span className="font-bold">{m.role}:</span> {m.text}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !disabled && send()}
          className="flex-1 px-3 py-2 rounded border border-aura-border bg-aura-background text-sm disabled:opacity-50"
          placeholder={disabled ? "Confidence review required" : "Ask about this portfolio..."}
          disabled={disabled}
        />
        <button
          onClick={send}
          disabled={busy || disabled}
          className="px-4 py-2 rounded bg-aura-navy text-white text-sm disabled:opacity-50"
        >
          {busy ? "..." : "Ask"}
        </button>
      </div>
    </div>
  );
}
