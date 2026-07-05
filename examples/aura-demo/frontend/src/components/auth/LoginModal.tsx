"use client";

import React, { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useAuth, type UserRole } from "./AuthContext";

interface LoginModalProps {
  open: boolean;
  onClose: () => void;
}

export function LoginModal({ open, onClose }: LoginModalProps) {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const firstRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setUsername("");
      setPassword("");
      setError(null);
      setTimeout(() => firstRef.current?.focus(), 0);
    }
  }, [open]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.login(username, password);
      login(res.access_token, res.username, res.role as UserRole);
      onClose();
    } catch (e: any) {
      setError(e?.message || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-aura-navy/40 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="login-title"
    >
      <div
        className="w-full max-w-sm bg-aura-surface border border-aura-border rounded-lg p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="login-title" className="font-mono text-lg font-bold text-aura-text mb-1">
          ASSURE Sign In
        </h2>
        <p className="text-xs text-aura-text-muted font-mono mb-4">
          Default demo: admin / admin
        </p>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <div>
            <label className="block text-xs font-mono text-aura-text-muted mb-1">Username</label>
            <input
              ref={firstRef}
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 rounded border border-aura-border bg-aura-background text-sm focus:outline-none focus:border-aura-navy"
              required
              autoComplete="username"
            />
          </div>
          <div>
            <label className="block text-xs font-mono text-aura-text-muted mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 rounded border border-aura-border bg-aura-background text-sm focus:outline-none focus:border-aura-navy"
              required
              autoComplete="current-password"
            />
          </div>
          {error && <p className="text-xs text-aura-crimson font-mono">{error}</p>}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={busy}
              className="flex-1 px-4 py-2 rounded bg-aura-navy text-white text-sm font-mono hover:bg-aura-navy/90 disabled:opacity-50"
            >
              {busy ? "Signing in…" : "Sign In"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded border border-aura-border text-aura-text-muted text-sm font-mono hover:bg-aura-surface-low"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
