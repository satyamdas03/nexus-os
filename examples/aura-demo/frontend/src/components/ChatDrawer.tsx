"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { clsx } from "clsx";
import { api } from "@/lib/api";
import type { ChatResponse, VoiceToken } from "@/lib/types";
import { Panel } from "@/components/ui/Panel";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { SecondaryButton } from "@/components/ui/SecondaryButton";
import { VoiceRoom } from "@/components/VoiceRoom";

interface Message {
  role: "user" | "assistant";
  text: string;
  citations?: Record<string, any>[];
  intent?: string;
}

export function ChatDrawer({
  clientId,
  clientName,
  open,
  onClose,
}: {
  clientId: string;
  clientName?: string;
  open: boolean;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      text: `Hi${clientName ? `, I'm reviewing ${clientName}` : ""}. Ask me why the portfolio is red, what a rule means, or "what if I buy 10 SPY?"`,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState<{ configured: boolean; message: string } | null>(null);
  const [inVoiceRoom, setInVoiceRoom] = useState(false);
  const [voiceToken, setVoiceToken] = useState<VoiceToken | null>(null);
  const [joiningVoice, setJoiningVoice] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  // Detect browser speech support once.
  useEffect(() => {
    const hasTTS = typeof window !== "undefined" && "speechSynthesis" in window;
    const hasSTT = typeof window !== "undefined" && !!(window as any).SpeechRecognition || !!(window as any).webkitSpeechRecognition;
    setVoiceEnabled(hasTTS || hasSTT);
    // Also check LiveKit backend status so we can show a real-voice badge if configured.
    api.voiceStatus().then(setVoiceStatus).catch(() => setVoiceStatus({ configured: false, message: "" }));
  }, []);

  const speak = useCallback((text: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.05;
    utterance.pitch = 1;
    window.speechSynthesis.speak(utterance);
  }, []);

  const send = useCallback(
    async (query: string) => {
      if (!query.trim()) return;
      setMessages((m) => [...m, { role: "user", text: query }]);
      setInput("");
      setLoading(true);
      try {
        const res: ChatResponse = await api.chat(clientId, query);
        const assistantMsg: Message = {
          role: "assistant",
          text: res.answer,
          citations: res.citations,
          intent: res.intent,
        };
        setMessages((m) => [...m, assistantMsg]);
        speak(res.answer);
      } catch (err) {
        setMessages((m) => [
          ...m,
          { role: "assistant", text: `Sorry, I couldn't reach the assurance engine. ${(err as Error).message}` },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [clientId, speak]
  );

  const startListening = useCallback(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) {
      setMessages((m) => [...m, { role: "assistant", text: "Voice input is not supported in this browser." }]);
      return;
    }
    const rec = new SR();
    rec.continuous = false;
    rec.interimResults = false;
    rec.lang = "en-US";
    rec.onstart = () => setListening(true);
    rec.onend = () => setListening(false);
    rec.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      send(transcript);
    };
    rec.onerror = () => setListening(false);
    recognitionRef.current = rec;
    rec.start();
  }, [send]);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setListening(false);
  }, []);

  const joinVoiceRoom = useCallback(async () => {
    setJoiningVoice(true);
    try {
      const token = await api.voiceToken(clientId);
      if (!token.configured || !token.token) {
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            text: "LiveKit voice is not configured on this deployment. I'll keep using your browser's built-in speech instead.",
          },
        ]);
        return;
      }
      setVoiceToken(token);
      setInVoiceRoom(true);
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: `Could not start a LiveKit voice session: ${(err as Error).message}. Browser speech fallback is still available.`,
        },
      ]);
    } finally {
      setJoiningVoice(false);
    }
  }, [clientId]);

  const leaveVoiceRoom = useCallback(() => {
    setInVoiceRoom(false);
    setVoiceToken(null);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    send(input);
  };

  const quickReply = (text: string) => send(text);

  const lastAssistant = messages.filter((m) => m.role === "assistant").pop();
  const followups = lastAssistant?.citations && lastAssistant.citations.length > 0
    ? ["Why is it red?", "What trade fixes this?", "Explain the top rule"]
    : ["Summarize the portfolio", "What is the cash position?", "What if I buy 10 SPY?"];

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} aria-hidden="true" />
      <div className="relative w-full max-w-md h-full bg-aura-surface-low shadow-aura-md flex flex-col animate-in slide-in-from-right duration-200">
        <Panel
          className="h-full rounded-none border-0 flex flex-col"
          header="Conversational Assurance"
          subheader={
            <span className="flex items-center gap-2">
              <span className={clsx("w-2 h-2 rounded-full", voiceStatus?.configured ? "bg-aura-emerald" : "bg-aura-slate-light")} />
              {voiceStatus?.configured ? "LiveKit voice ready" : "Browser voice fallback"}
            </span>
          }
          right={
            <button onClick={onClose} className="material-symbols-outlined text-aura-slate hover:text-aura-navy" aria-label="Close chat">
              close
            </button>
          }
        >
          <div className="flex-1 overflow-y-auto pr-1" ref={scrollRef}>
            <div className="space-y-4">
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={clsx(
                    "rounded p-3 text-sm whitespace-pre-wrap",
                    m.role === "user" ? "bg-aura-navy text-white self-end ml-8" : "bg-white border border-aura-border self-start mr-8"
                  )}
                >
                  {m.text}
                  {m.citations && m.citations.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-aura-border text-xs text-aura-slate">
                      Grounded in {m.citations.length} engine fact{m.citations.length > 1 ? "s" : ""}
                      {m.intent ? ` • intent: ${m.intent}` : ""}
                    </div>
                  )}
                </div>
              ))}
              {loading && (
                <div className="bg-white border border-aura-border rounded p-3 text-sm text-aura-slate flex items-center gap-2">
                  <span className="material-symbols-outlined animate-spin text-[16px]">progress_activity</span>
                  Checking the rules engine…
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-aura-border">
            <div className="flex flex-wrap gap-2 mb-3">
              {followups.slice(0, 3).map((text) => (
                <button
                  key={text}
                  onClick={() => quickReply(text)}
                  className="px-2 py-1 rounded border border-aura-border text-xs text-aura-navy hover:bg-aura-surface transition-colors"
                >
                  {text}
                </button>
              ))}
            </div>

            {inVoiceRoom && voiceToken && (
              <VoiceRoom
                url={voiceToken.url}
                token={voiceToken.token}
                room={voiceToken.room}
                identity={voiceToken.identity}
                onLeave={leaveVoiceRoom}
              />
            )}

            <form onSubmit={handleSubmit} className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about the portfolio…"
                className="flex-1 px-3 py-2 rounded border border-aura-border bg-white text-sm focus:outline-none focus:border-aura-navy"
                disabled={inVoiceRoom}
              />
              {voiceEnabled && !inVoiceRoom && (
                <SecondaryButton
                  onClick={listening ? stopListening : startListening}
                  className={clsx(listening && "bg-aura-crimson-soft border-aura-crimson text-aura-crimson")}
                >
                  <span className="material-symbols-outlined text-[18px]">{listening ? "mic_off" : "mic"}</span>
                </SecondaryButton>
              )}
              {voiceStatus?.configured && !inVoiceRoom && (
                <SecondaryButton onClick={joinVoiceRoom} loading={joiningVoice}>
                  <span className="material-symbols-outlined text-[18px]">headset_mic</span>
                </SecondaryButton>
              )}
              <PrimaryButton type="submit" loading={loading} disabled={inVoiceRoom}>
                <span className="material-symbols-outlined text-[18px]">send</span>
              </PrimaryButton>
            </form>
          </div>
        </Panel>
      </div>
    </div>
  );
}
