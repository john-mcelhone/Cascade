/**
 * Flow Path PD page state.
 *
 * Holds:
 *  - Per-project parameter table state (parameters keyed by project id so
 *    the table survives navigation away/back).
 *  - The picked candidate and the currently selected loss model.
 *  - Streamed candidates from the most recent exploration job.
 *  - 3D viewer settings (display mode, section clipping, theme).
 *  - Three-pane divider positions (persisted to localStorage).
 *  - The currently-running exploration job id + progress.
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { ServerCandidate } from "@/lib/api/flowpath";
import { DEFAULT_PARAMETERS, type ParameterDef } from "./parameters";

export type DisplayMode = "solid" | "wireframe" | "section";
export type ShadingMode = "photoreal" | "linedrawing";
/**
 * Which parameter section is currently shown in the left pane. The left pane
 * stacks five categories that used to render simultaneously (cramped on a
 * 14" laptop); tabbing them keeps the pane scannable.
 */
export type ParameterTabKey =
  | "boundary"
  | "geometry"
  | "constraint"
  | "exploration"
  | "loss-model";

export interface FlowPathPaneLayout {
  /** Width of the left pane in CSS pixels. */
  leftWidth: number;
  /** Width of the right (3D viewer) pane in CSS pixels. */
  rightWidth: number;
}

export interface FlowPathState {
  // ---- Parameter table ----
  parametersByProject: Record<string, ParameterDef[]>;
  getParameters: (projectId: string) => ParameterDef[];
  setParameter: (
    projectId: string,
    id: string,
    patch: Partial<ParameterDef>,
  ) => void;
  resetParameters: (projectId: string) => void;

  // ---- Loss model ----
  lossModelName: string;
  setLossModel: (name: string) => void;
  lossScales: Record<string, number>;
  setLossScale: (component: string, value: number) => void;

  // ---- Candidates ----
  candidates: ServerCandidate[];
  appendCandidates: (cs: ServerCandidate[]) => void;
  resetCandidates: () => void;

  // ---- Scatter selection ----
  pickedCandidateId: string | null;
  setPicked: (id: string | null) => void;
  brushedCandidateIds: string[] | null;
  setBrushed: (ids: string[] | null) => void;

  // ---- Scatter axes ----
  scatterX: string;
  scatterY: string;
  scatterColor: string;
  setScatterAxes: (axes: Partial<{ x: string; y: string; color: string }>) => void;

  // ---- Scatter filter (W-09) ----
  /** Raw filter expression string, e.g. "eta_tt > 0.85 AND N < 60000". */
  scatterFilter: string;
  setScatterFilter: (filter: string) => void;

  // ---- 3D viewer ----
  displayMode: DisplayMode;
  shading: ShadingMode;
  showHud: boolean;
  setDisplayMode: (m: DisplayMode) => void;
  setShading: (s: ShadingMode) => void;

  // ---- Left-pane tab + scatter parallel-coords toggle (persisted) ----
  parameterTab: ParameterTabKey;
  setParameterTab: (t: ParameterTabKey) => void;
  showParallelCoords: boolean;
  setShowParallelCoords: (v: boolean) => void;

  // ---- Job tracking ----
  jobId: string | null;
  jobProgress: number;
  jobStatus: "idle" | "running" | "done" | "failed" | "cancelled";
  jobMessage: string;
  setJob: (patch: {
    jobId?: string | null;
    progress?: number;
    status?: FlowPathState["jobStatus"];
    message?: string;
  }) => void;

  // ---- Pane layout (persisted) ----
  layout: FlowPathPaneLayout;
  setLayout: (patch: Partial<FlowPathPaneLayout>) => void;
}

export const useFlowPathStore = create<FlowPathState>()(
  persist(
    (set, get) => ({
      parametersByProject: {},
      // PURE selector — never mutates state. Returns the project-specific
      // entry when present, otherwise the shared DEFAULT_PARAMETERS module
      // reference (also stable). The first edit on a project seeds the
      // project-specific copy via setParameter below.
      //
      // Earlier versions called `set` from inside this method and the call
      // sites used it inside a `useFlowPathStore((s) => ...)` selector,
      // which produced an infinite render loop ("Maximum update depth
      // exceeded"). Never trigger state writes from selectors.
      getParameters: (projectId) =>
        get().parametersByProject[projectId] ?? DEFAULT_PARAMETERS,
      setParameter: (projectId, id, patch) =>
        set((s) => {
          // Lazy-seed the per-project array on first edit so subsequent
          // edits compose correctly against the seeded defaults.
          const current =
            s.parametersByProject[projectId] ??
            DEFAULT_PARAMETERS.map((p) => ({ ...p }));
          const next = current.map((p) => (p.id === id ? { ...p, ...patch } : p));
          return {
            parametersByProject: { ...s.parametersByProject, [projectId]: next },
          };
        }),
      resetParameters: (projectId) =>
        set((s) => ({
          parametersByProject: {
            ...s.parametersByProject,
            [projectId]: DEFAULT_PARAMETERS.map((p) => ({ ...p })),
          },
        })),

      lossModelName: "whitfield-baines-radial-v1",
      setLossModel: (name) => set({ lossModelName: name }),
      lossScales: {},
      setLossScale: (component, value) =>
        set((s) => ({ lossScales: { ...s.lossScales, [component]: value } })),

      candidates: [],
      appendCandidates: (cs) =>
        set((s) => {
          const known = new Set(s.candidates.map((c) => c.id));
          const fresh = cs.filter((c) => !known.has(c.id));
          if (fresh.length === 0) return {};
          return { candidates: [...s.candidates, ...fresh] };
        }),
      resetCandidates: () =>
        set({ candidates: [], pickedCandidateId: null, brushedCandidateIds: null }),

      pickedCandidateId: null,
      setPicked: (id) => set({ pickedCandidateId: id }),
      brushedCandidateIds: null,
      setBrushed: (ids) => set({ brushedCandidateIds: ids }),

      scatterX: "rotor_outlet_radius",
      scatterY: "eta_tt",
      scatterColor: "eta_tt",
      setScatterAxes: (axes) =>
        set((s) => ({
          scatterX: axes.x ?? s.scatterX,
          scatterY: axes.y ?? s.scatterY,
          scatterColor: axes.color ?? s.scatterColor,
        })),

      scatterFilter: "",
      setScatterFilter: (filter) => set({ scatterFilter: filter }),

      displayMode: "solid",
      shading: "photoreal",
      showHud: true,
      setDisplayMode: (m) => set({ displayMode: m }),
      setShading: (s) => set({ shading: s }),

      parameterTab: "boundary",
      setParameterTab: (t) => set({ parameterTab: t }),
      showParallelCoords: false,
      setShowParallelCoords: (v) => set({ showParallelCoords: v }),

      jobId: null,
      jobProgress: 0,
      jobStatus: "idle",
      jobMessage: "",
      setJob: (patch) =>
        set((s) => ({
          jobId: patch.jobId === undefined ? s.jobId : patch.jobId,
          jobProgress: patch.progress ?? s.jobProgress,
          jobStatus: patch.status ?? s.jobStatus,
          jobMessage: patch.message ?? s.jobMessage,
        })),

      layout: { leftWidth: 420, rightWidth: 360 },
      setLayout: (patch) =>
        set((s) => ({ layout: { ...s.layout, ...patch } })),
    }),
    {
      name: "cascade.flowpath",
      storage: createJSONStorage(() => localStorage),
      // Only persist user preferences and pane geometry; never restore the
      // streaming candidates from a previous session.
      partialize: (s) => ({
        layout: s.layout,
        scatterX: s.scatterX,
        scatterY: s.scatterY,
        scatterColor: s.scatterColor,
        scatterFilter: s.scatterFilter,
        displayMode: s.displayMode,
        shading: s.shading,
        lossModelName: s.lossModelName,
        lossScales: s.lossScales,
        parameterTab: s.parameterTab,
        showParallelCoords: s.showParallelCoords,
      }),
    },
  ),
);
