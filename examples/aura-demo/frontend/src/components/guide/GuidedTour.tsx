"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { clsx } from "clsx";
import { api } from "@/lib/api";
import { TOUR_STEPS, useTour, getTourPortfolio, setTourPortfolio } from "./useTour";

const MARGIN = 16;

function findTarget(selector: string): HTMLElement | null {
  if (typeof document === "undefined") return null;
  return document.querySelector(selector) as HTMLElement | null;
}

function getStepUrl(step: number, portfolioId: string | null): string | null {
  const route = TOUR_STEPS[step]?.route;
  if (!route) return null;
  if (route === "/") return "/?tour_step=" + step;
  if (route === "/portfolio/:id") {
    const id = portfolioId ?? "1";
    return `/portfolio/${id}?tour_step=${step}`;
  }
  if (route === "/portfolio/:id/workbench") {
    const id = portfolioId ?? "1";
    return `/portfolio/${id}/workbench?tour_step=${step}`;
  }
  if (route === "/hermes") return "/hermes?tour_step=" + step;
  return null;
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

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(n, max));
}

type Rect = {
  top: number;
  left: number;
  right: number;
  bottom: number;
  width: number;
  height: number;
};

export function GuidedTour() {
  const router = useRouter();
  const pathname = usePathname();
  const { active, step, ready, next, prev, stop, go } = useTour();
  const [rect, setRect] = useState<Rect | null>(null);
  const [targetFound, setTargetFound] = useState(false);
  const [navigating, setNavigating] = useState(false);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const pollingRef = useRef<number | null>(null);
  const currentStep = TOUR_STEPS[step];

  // Resolve a portfolio for the tour once when we first need it.
  useEffect(() => {
    if (!active || !ready) return;
    if (getTourPortfolio()) return;
    api.listPortfolios(50, 0)
      .then((ps) => {
        const pick = ps.find((p) => p.status !== "green") ?? ps[0];
        if (pick) setTourPortfolio(pick.client_id);
      })
      .catch(() => {});
  }, [active, ready]);

  // If the current step belongs to a different route, navigate there.
  useEffect(() => {
    if (!active || !ready || !currentStep) return;
    if (routeMatchesStep(pathname, step)) return;
    const pid = getTourPortfolio();
    const url = getStepUrl(step, pid);
    if (url && url !== window.location.pathname + window.location.search) {
      setNavigating(true);
      router.push(url);
    }
  }, [active, ready, pathname, step, currentStep, router]);

  // Poll target position and scroll it into view when found.
  useLayoutEffect(() => {
    if (!active || !ready || !currentStep) {
      setRect(null);
      setTargetFound(false);
      return;
    }

    let foundOnce = false;

    const update = () => {
      const el = findTarget(currentStep.selector);
      setTargetFound(!!el);
      if (el) {
        const box = el.getBoundingClientRect();
        setRect({
          top: box.top,
          left: box.left,
          right: box.right,
          bottom: box.bottom,
          width: box.width,
          height: box.height,
        });
        setNavigating(false);
        if (!foundOnce) {
          foundOnce = true;
          el.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
        }
      }
    };

    update();
    pollingRef.current = window.setInterval(update, 200);
    return () => {
      if (pollingRef.current) window.clearInterval(pollingRef.current);
    };
  }, [active, ready, currentStep, pathname, step]);

  // Re-measure tooltip position on scroll/resize.
  useEffect(() => {
    if (!active) return;
    const onLayout = () => {
      if (!currentStep) return;
      const el = findTarget(currentStep.selector);
      if (el) {
        const box = el.getBoundingClientRect();
        setRect({
          top: box.top,
          left: box.left,
          right: box.right,
          bottom: box.bottom,
          width: box.width,
          height: box.height,
        });
      }
    };
    window.addEventListener("resize", onLayout);
    window.addEventListener("scroll", onLayout, true);
    return () => {
      window.removeEventListener("resize", onLayout);
      window.removeEventListener("scroll", onLayout, true);
    };
  }, [active, currentStep]);

  if (!active || !ready || !currentStep) return null;

  const box = rect;
  const tooltipEl = tooltipRef.current;
  const tw = tooltipEl?.offsetWidth ?? 320;
  const th = tooltipEl?.offsetHeight ?? 160;
  const vw = window.innerWidth;
  const vh = window.innerHeight;

  let tooltipTop = vh / 2 - th / 2;
  let tooltipLeft = vw / 2 - tw / 2;

  if (box) {
    switch (currentStep.placement) {
      case "top":
        tooltipTop = box.top - th - MARGIN;
        tooltipLeft = box.left + box.width / 2 - tw / 2;
        break;
      case "left":
        tooltipTop = box.top + box.height / 2 - th / 2;
        tooltipLeft = box.left - tw - MARGIN;
        break;
      case "right":
        tooltipTop = box.top + box.height / 2 - th / 2;
        tooltipLeft = box.right + MARGIN;
        break;
      case "bottom":
      default:
        tooltipTop = box.bottom + MARGIN;
        tooltipLeft = box.left + box.width / 2 - tw / 2;
        break;
    }
    // Flip if overflow. Prefer opposite side, otherwise clamp to viewport.
    if (tooltipTop < MARGIN) {
      if (currentStep.placement === "top" && box.bottom + MARGIN + th <= vh - MARGIN) {
        tooltipTop = box.bottom + MARGIN;
      } else {
        tooltipTop = MARGIN;
      }
    }
    if (tooltipTop + th > vh - MARGIN) {
      tooltipTop = vh - th - MARGIN;
    }
    if (tooltipLeft < MARGIN) {
      if (currentStep.placement === "left" && box.right + MARGIN + tw <= vw - MARGIN) {
        tooltipLeft = box.right + MARGIN;
      } else {
        tooltipLeft = MARGIN;
      }
    }
    if (tooltipLeft + tw > vw - MARGIN) {
      if (currentStep.placement === "right" && box.left - tw - MARGIN >= MARGIN) {
        tooltipLeft = box.left - tw - MARGIN;
      } else {
        tooltipLeft = vw - tw - MARGIN;
      }
    }
  }

  tooltipTop = clamp(tooltipTop, MARGIN, vh - th - MARGIN);
  tooltipLeft = clamp(tooltipLeft, MARGIN, vw - tw - MARGIN);

  return (
    <div className="fixed inset-0 z-[60] pointer-events-none">
      {/* dark backdrop with cutout */}
      <div className="absolute inset-0 bg-aura-navy/40 pointer-events-auto" />
      {box && (
        <div
          className="absolute bg-transparent border-2 border-aura-navy rounded shadow-[0_0_0_9999px_rgba(15,23,42,0.4)] pointer-events-none transition-all duration-200"
          style={{
            top: box.top - 8,
            left: box.left - 8,
            width: box.width + 16,
            height: box.height + 16,
          }}
        />
      )}

      {/* tooltip */}
      <div
        ref={tooltipRef}
        className="absolute w-80 max-w-[calc(100vw-32px)] bg-aura-surface border border-aura-border rounded shadow-xl p-4 pointer-events-auto"
        style={{ top: tooltipTop, left: tooltipLeft, transition: "top 150ms ease-out, left 150ms ease-out" }}
      >
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3 className="font-mono text-sm font-bold text-aura-navy">{currentStep.title}</h3>
          <button
            onClick={stop}
            className="text-aura-text-muted hover:text-aura-crimson"
            aria-label="Close tour"
          >
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>
        <p className="font-mono text-xs text-aura-text leading-relaxed mb-4">{currentStep.body}</p>

        {!targetFound && !navigating && (
          <p className="font-mono text-[10px] text-aura-ochre mb-3 flex items-center gap-1.5">
            <span className="material-symbols-outlined text-[14px]">warning</span>
            Scrolling to highlight…
          </p>
        )}
        {navigating && (
          <p className="font-mono text-[10px] text-aura-navy mb-3 flex items-center gap-1.5">
            <span className="material-symbols-outlined text-[14px] animate-spin">progress_activity</span>
            Moving to the next screen…
          </p>
        )}

        <div className="flex items-center justify-between">
          <div className="flex gap-1">
            {TOUR_STEPS.map((_, i) => (
              <button
                key={i}
                onClick={() => go(i)}
                className={clsx(
                  "w-2 h-2 rounded-full",
                  i === step ? "bg-aura-navy" : "bg-aura-slate hover:bg-aura-text-muted"
                )}
                aria-label={`Go to step ${i + 1}`}
              />
            ))}
          </div>
          <div className="flex gap-2">
            <button
              onClick={prev}
              disabled={step === 0}
              className="px-2 py-1 rounded border border-aura-border text-aura-text-muted font-mono text-xs hover:border-aura-navy hover:text-aura-navy disabled:opacity-40"
            >
              Back
            </button>
            {step === TOUR_STEPS.length - 1 ? (
              <button
                onClick={stop}
                className="px-3 py-1 rounded bg-aura-navy text-white font-mono text-xs hover:bg-aura-navy/90"
              >
                Finish
              </button>
            ) : (
              <button
                onClick={next}
                className="px-3 py-1 rounded bg-aura-navy text-white font-mono text-xs hover:bg-aura-navy/90"
              >
                Next
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
