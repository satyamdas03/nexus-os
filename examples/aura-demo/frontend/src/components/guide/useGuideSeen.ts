"use client";

import { useEffect, useState } from "react";

const KEY = "assure_guide_seen";

export function useGuideSeen() {
  const [seen, setSeen] = useState(true);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      // sessionStorage = shown per browser session (new tab/incognito/reopen), not every refresh
      setSeen(window.sessionStorage.getItem(KEY) === "1");
      setReady(true);
    }
  }, []);

  const markSeen = () => {
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem(KEY, "1");
    }
    setSeen(true);
  };

  const reset = () => {
    if (typeof window !== "undefined") {
      window.sessionStorage.removeItem(KEY);
    }
    setSeen(false);
  };

  return { seen, ready, markSeen, reset };
}
