"use client";

import { useAuth } from "./AuthContext";

export function useMutationGuard(): { disabled: boolean; title?: string } {
  const { canMutate } = useAuth();
  return canMutate ? { disabled: false } : { disabled: true, title: "Viewers cannot modify state" };
}
