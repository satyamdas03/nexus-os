"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

export type UserRole = "viewer" | "adviser" | "admin" | null;

interface AuthState {
  token: string | null;
  username: string | null;
  role: UserRole;
  login: (token: string, username: string, role: UserRole) => void;
  logout: () => void;
  canMutate: boolean;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

const STORAGE_KEY = "assure_auth";

function _load(): { token: string | null; username: string | null; role: UserRole } {
  if (typeof window === "undefined") return { token: null, username: null, role: null };
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return { token: null, username: null, role: null };
    const parsed = JSON.parse(raw);
    return {
      token: parsed.token || null,
      username: parsed.username || null,
      role: parsed.role || null,
    };
  } catch {
    return { token: null, username: null, role: null };
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);
  const [role, setRole] = useState<UserRole>(null);

  useEffect(() => {
    const loaded = _load();
    setToken(loaded.token);
    setUsername(loaded.username);
    setRole(loaded.role);
  }, []);

  const login = (t: string, u: string, r: UserRole) => {
    setToken(t);
    setUsername(u);
    setRole(r);
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ token: t, username: u, role: r }));
    }
  };

  const logout = () => {
    setToken(null);
    setUsername(null);
    setRole(null);
    if (typeof window !== "undefined") {
      window.sessionStorage.removeItem(STORAGE_KEY);
    }
  };

  const value: AuthState = {
    token,
    username,
    role,
    login,
    logout,
    canMutate: role === "adviser" || role === "admin",
    isAdmin: role === "admin",
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
