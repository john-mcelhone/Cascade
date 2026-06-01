"use client";

import { useUIStore } from "@/lib/stores/ui-store";
import { useMounted } from "@/lib/hooks/use-mounted";

/**
 * Coaching policy derived from the current experience level.
 *
 *  - guided:   inline coach marks + next-step nudges are shown by default.
 *  - standard: coaching is available on demand (tooltips), not pushed inline.
 *  - expert:   no coaching surfaces at all.
 *
 * SSR renders as the "guided" default to match the persisted initial state.
 */
export function useCoaching() {
  const mounted = useMounted();
  const experience = useUIStore((s) => s.experience);
  const level = mounted ? experience : "guided";

  return {
    level,
    /** Show inline, always-visible coaching (guided only). */
    showInlineCoaching: level === "guided",
    /** Density: roomier in guided, tightest in expert. */
    roomy: level === "guided",
    dense: level === "expert",
  };
}
