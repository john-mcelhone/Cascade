import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export type JobStatus = "idle" | "running" | "succeeded" | "failed" | "cancelled";

/**
 * Experience level — the single dial that adapts the whole product across the
 * beginner→professional range. It governs UI density, how much inline coaching
 * is shown, and how aggressively advanced controls are disclosed.
 *
 *  - "guided"   Absolute beginners. Roomy layout, plain-language coaching,
 *               next-step nudges, advanced controls hidden behind "Show more".
 *  - "standard" The default working mode. Balanced density, coaching on
 *               demand (hover/tooltip), everything reachable.
 *  - "expert"   Professionals. Maximum density, keyboard-first, no nudges,
 *               every control surfaced at once.
 */
export type ExperienceLevel = "guided" | "standard" | "expert";

export const EXPERIENCE_LEVELS: {
  id: ExperienceLevel;
  label: string;
  blurb: string;
}[] = [
  {
    id: "guided",
    label: "Guided",
    blurb: "Roomy layout with plain-language coaching and next-step nudges.",
  },
  {
    id: "standard",
    label: "Standard",
    blurb: "Balanced density. Help on demand. Everything within reach.",
  },
  {
    id: "expert",
    label: "Expert",
    blurb: "Maximum density, keyboard-first, no nudges. Every control at once.",
  },
];

export interface JobState {
  id: string | null;
  label: string;
  status: JobStatus;
  progress: number; // 0..1
  residual: number | null;
  iteration: number;
  // E.g. "1,287 of 2,000 candidates"
  detail?: string;
}

export interface UIState {
  // Left-rail collapsed / expanded.
  railCollapsed: boolean;
  setRailCollapsed: (collapsed: boolean) => void;
  toggleRail: () => void;

  // Command palette open state.
  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;

  // Experience level — drives density + coaching across the app.
  experience: ExperienceLevel;
  setExperience: (level: ExperienceLevel) => void;

  // First-run onboarding (the welcome flow on /projects). Once dismissed or
  // completed it stays dismissed across sessions.
  onboardingDismissed: boolean;
  dismissOnboarding: () => void;
  resetOnboarding: () => void;

  // Per-key dismissal of inline coach marks (guided mode hints). A hint that's
  // been dismissed never returns.
  dismissedHints: Record<string, boolean>;
  dismissHint: (key: string) => void;

  // Active solver job (drives the bottom bar).
  job: JobState;
  setJob: (next: Partial<JobState>) => void;
  resetJob: () => void;
}

const idleJob: JobState = {
  id: null,
  label: "",
  status: "idle",
  progress: 0,
  residual: null,
  iteration: 0,
};

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      railCollapsed: false,
      setRailCollapsed: (collapsed) => set({ railCollapsed: collapsed }),
      toggleRail: () =>
        set((s) => ({ railCollapsed: !s.railCollapsed })),

      paletteOpen: false,
      setPaletteOpen: (open) => set({ paletteOpen: open }),

      experience: "guided",
      setExperience: (level) => set({ experience: level }),

      onboardingDismissed: false,
      dismissOnboarding: () => set({ onboardingDismissed: true }),
      resetOnboarding: () => set({ onboardingDismissed: false }),

      dismissedHints: {},
      dismissHint: (key) =>
        set((s) => ({ dismissedHints: { ...s.dismissedHints, [key]: true } })),

      job: idleJob,
      setJob: (next) =>
        set((s) => ({ job: { ...s.job, ...next } })),
      resetJob: () => set({ job: idleJob }),
    }),
    {
      name: "cascade.ui",
      // Only persist what's actually a user preference; not in-flight jobs / palette.
      partialize: (s) => ({
        railCollapsed: s.railCollapsed,
        experience: s.experience,
        onboardingDismissed: s.onboardingDismissed,
        dismissedHints: s.dismissedHints,
      }),
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
