"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { VoiceRoom } from "@/components/VoiceRoom";

export function AdviserControls({ clientId, onLeave }: { clientId: string; onLeave?: () => void }) {
  const [token, setToken] = useState<string | null>(null);
  const [url, setUrl] = useState("");
  const [room, setRoom] = useState("");
  const [identity, setIdentity] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const join = async () => {
    try {
      const res = await api.adviser.session(clientId);
      setToken(res.token);
      setUrl(res.url);
      setRoom(res.room);
      setIdentity(res.identity);
      setErr(null);
    } catch (e: any) {
      setErr(e.message || "Voice session failed");
    }
  };

  if (token) {
    return (
      <VoiceRoom
        url={url}
        token={token}
        room={room}
        identity={identity}
        onLeave={() => { setToken(null); onLeave?.(); }}
      />
    );
  }

  return (
    <div className="bg-aura-surface border border-aura-border rounded p-4 space-y-2">
      {err && <p className="text-xs text-aura-crimson font-mono">{err}</p>}
      <button
        onClick={join}
        className="px-4 py-2 rounded bg-aura-navy text-white text-sm flex items-center gap-2"
      >
        <span className="material-symbols-outlined text-[18px]">headset_mic</span>
        Join voice session
      </button>
    </div>
  );
}
