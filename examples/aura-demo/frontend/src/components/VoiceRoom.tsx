"use client";

import React, { useEffect, useState } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useConnectionState,
  useLocalParticipant,
} from "@livekit/components-react";
import { clsx } from "clsx";

interface VoiceRoomProps {
  url: string;
  token: string;
  room: string;
  identity: string;
  onLeave?: () => void;
}

function VoiceRoomControls({ onLeave }: { onLeave?: () => void }) {
  const { localParticipant } = useLocalParticipant();
  const connectionState = useConnectionState();
  const [micEnabled, setMicEnabled] = useState(localParticipant.isMicrophoneEnabled);

  useEffect(() => {
    setMicEnabled(localParticipant.isMicrophoneEnabled);
  }, [localParticipant.isMicrophoneEnabled]);

  const toggleMic = async () => {
    try {
      await localParticipant.setMicrophoneEnabled(!micEnabled);
    } catch {
      // Permissions may be denied; state will reflect actual device status.
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 text-sm text-aura-slate">
        <span
          className={clsx(
            "w-2 h-2 rounded-full",
            connectionState === "connected" ? "bg-aura-emerald" : "bg-aura-amber"
          )}
        />
        {connectionState === "connected" ? "Voice room connected" : `Voice room ${connectionState}`}
      </div>
      <div className="flex gap-2">
        <button
          onClick={toggleMic}
          className={clsx(
            "flex items-center gap-1 px-3 py-2 rounded text-sm border transition-colors",
            micEnabled
              ? "bg-aura-navy text-white border-aura-navy"
              : "bg-white text-aura-slate border-aura-border hover:border-aura-navy"
          )}
        >
          <span className="material-symbols-outlined text-[18px]">{micEnabled ? "mic" : "mic_off"}</span>
          {micEnabled ? "Mute" : "Unmute"}
        </button>
        <button
          onClick={onLeave}
          className="flex items-center gap-1 px-3 py-2 rounded text-sm border border-aura-crimson text-aura-crimson bg-aura-crimson-soft hover:bg-aura-crimson hover:text-white transition-colors"
        >
          <span className="material-symbols-outlined text-[18px]">call_end</span>
          Leave
        </button>
      </div>
      <p className="text-xs text-aura-slate">
        LiveKit room: <span className="font-medium text-aura-navy">{location.hostname}</span> is connected as{" "}
        <span className="font-medium text-aura-navy">{localParticipant.identity}</span>. A server-side agent will
        join here to listen and respond.
      </p>
    </div>
  );
}

export function VoiceRoom({ url, token, room, identity, onLeave }: VoiceRoomProps) {
  return (
    <LiveKitRoom serverUrl={url} token={token} connectOptions={{ autoSubscribe: true }} data-lk-theme="default">
      <div className="rounded border border-aura-border bg-white p-3 mb-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-aura-navy">LiveKit voice session</span>
          <span className="text-xs text-aura-slate">{room}</span>
        </div>
        <VoiceRoomControls onLeave={onLeave} />
      </div>
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}
