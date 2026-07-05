"use client";

import { useEffect, useState } from "react";

const ACTIVE_KEY = "assure_tour_active";
const STEP_KEY = "assure_tour_step";
const PORTFOLIO_KEY = "assure_tour_portfolio";

const START_EVENT = "assure:start-tour";
const STOP_EVENT = "assure:stop-tour";
const GO_EVENT = "assure:go-tour-step";

export type TourStep = {
  id: string;
  title: string;
  body: string;
  route: string;
  selector: string;
  placement?: "bottom" | "top" | "left" | "right";
};

export const TOUR_STEPS: TourStep[] = [
  {
    id: "heatmap",
    title: "1 / 6 · Command Centre heatmap",
    body:
      "Each block is one portfolio, sized by funds under management and coloured by the deterministic rules engine: green = aligned, orange = drift watch, red = breach.",
    route: "/",
    selector: '[data-tour="heatmap"]',
    placement: "bottom",
  },
  {
    id: "triage",
    title: "2 / 6 · Urgent Triage",
    body:
      "Portfolios are ranked by severity and money at risk. Click any red or orange block next to inspect why the rules engine flagged it.",
    route: "/",
    selector: '[data-tour="triage"]',
    placement: "left",
  },
  {
    id: "narrative",
    title: "3 / 6 · Assurance Narrative",
    body:
      "The AI writes plain-English advice, but only from breaches the deterministic rules engine actually found. The confidence line shows what is rule-maths vs advisory.",
    route: "/portfolio/:id",
    selector: '[data-tour="narrative"]',
    placement: "bottom",
  },
  {
    id: "strategy",
    title: "4 / 6 · AI Remediation Strategy",
    body:
      "The AI proposes minimal compliant trades. Every proposal is re-verified by the rules engine before a human sees it.",
    route: "/portfolio/:id/workbench",
    selector: '[data-tour="strategy"]',
    placement: "bottom",
  },
  {
    id: "cage",
    title: "5 / 6 · Assurance Cage",
    body:
      "AI proposes → rules engine verifies → human approves. Approval is blocked until the post-trade portfolio is COMPLIANT.",
    route: "/portfolio/:id/workbench",
    selector: '[data-tour="verify"]',
    placement: "left",
  },
  {
    id: "hermes",
    title: "6 / 6 · Hermes Scale",
    body:
      "Hermes runs the same propose → verify → approve cage across the whole book. Scan Book queues rules-green trades; nothing auto-executes and the mandate itself is locked.",
    route: "/hermes",
    selector: '[data-tour="hermes"]',
    placement: "bottom",
  },
];

function readStep(): number {
  if (typeof window === "undefined") return 0;
  const raw = window.sessionStorage.getItem(STEP_KEY);
  const parsed = raw ? parseInt(raw, 10) : NaN;
  return Number.isNaN(parsed) ? 0 : Math.max(0, Math.min(parsed, TOUR_STEPS.length - 1));
}

function readActive(): boolean {
  if (typeof window === "undefined") return false;
  return window.sessionStorage.getItem(ACTIVE_KEY) === "1";
}

function routeMatchesStep(pathname: string, step: number): boolean {
  const route = TOUR_STEPS[step]?.route;
  if (!route) return false;
  if (route === "/") return pathname === "/";
  if (route === "/portfolio/:id") return /^\/portfolio\/[^/]+$/.test(pathname);
  if (route === "/portfolio/:id/workbench") return pathname.endsWith("/workbench");
  if (route === "/hermes") return pathname === "/hermes";
  return false;
}

function updateUrlForStep(step: number) {
  if (typeof window === "undefined") return;
  const pathname = window.location.pathname;
  if (!routeMatchesStep(pathname, step)) return; // route navigation will set the param
  const url = new URL(window.location.href);
  url.searchParams.set("tour_step", String(step));
  window.history.replaceState(window.history.state, "", url.toString());
}

export function useTour() {
  const [active, setActive] = useState(false);
  const [step, setStep] = useState(0);
  const [ready, setReady] = useState(false);

  // Sync with sessionStorage and cross-instance events.
  useEffect(() => {
    if (typeof window === "undefined") return;
    setActive(readActive());
    setStep(readStep());
    setReady(true);

    const onStart = () => {
      setActive(true);
      setStep(0);
    };
    const onStop = () => {
      setActive(false);
    };
    const onGo = (e: Event) => {
      const next = (e as CustomEvent).detail?.step ?? readStep();
      setStep(next);
      setActive(true);
    };

    window.addEventListener(START_EVENT, onStart);
    window.addEventListener(STOP_EVENT, onStop);
    window.addEventListener(GO_EVENT, onGo);
    return () => {
      window.removeEventListener(START_EVENT, onStart);
      window.removeEventListener(STOP_EVENT, onStop);
      window.removeEventListener(GO_EVENT, onGo);
    };
  }, []);

  const persist = (nextActive: boolean, nextStep: number) => {
    if (typeof window === "undefined") return;
    window.sessionStorage.setItem(ACTIVE_KEY, nextActive ? "1" : "0");
    window.sessionStorage.setItem(STEP_KEY, String(nextStep));
  };

  const broadcastStart = () => {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(START_EVENT));
    }
  };

  const broadcastStop = () => {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(STOP_EVENT));
    }
  };

  const broadcastGo = (nextStep: number) => {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(GO_EVENT, { detail: { step: nextStep } }));
    }
  };

  const start = () => {
    persist(true, 0);
    updateUrlForStep(0);
    setActive(true);
    setStep(0);
    broadcastStart();
  };

  const stop = () => {
    persist(false, 0);
    sessionStorage.removeItem(ACTIVE_KEY);
    sessionStorage.removeItem(STEP_KEY);
    sessionStorage.removeItem(PORTFOLIO_KEY);
    setActive(false);
    broadcastStop();
  };

  const go = (nextStep: number) => {
    const clamped = Math.max(0, Math.min(nextStep, TOUR_STEPS.length - 1));
    persist(active, clamped);
    updateUrlForStep(clamped);
    setStep(clamped);
    broadcastGo(clamped);
  };

  const next = () => go(step + 1);
  const prev = () => go(step - 1);

  return { active, step, ready, start, stop, next, prev, go };
}

export function dispatchStartTour() {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(ACTIVE_KEY, "1");
  window.sessionStorage.setItem(STEP_KEY, "0");
  updateUrlForStep(0);
  window.dispatchEvent(new CustomEvent(START_EVENT));
}

export function getTourPortfolio(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(PORTFOLIO_KEY);
}

export function setTourPortfolio(id: string) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(PORTFOLIO_KEY, id);
}
