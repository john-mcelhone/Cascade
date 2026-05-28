import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export type JobStatus = "idle" | "running" | "succeeded" | "failed" | "cancelled";

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

      job: idleJob,
      setJob: (next) =>
        set((s) => ({ job: { ...s.job, ...next } })),
      resetJob: () => set({ job: idleJob }),
    }),
    {
      name: "cascade.ui",
      // Only persist what's actually a user preference; not in-flight jobs / palette.
      partialize: (s) => ({ railCollapsed: s.railCollapsed }),
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
