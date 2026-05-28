"use client";

/**
 * Zustand store local to the Cycle Canvas. Persists only what shouldn't
 * round-trip through the API: which node is selected, whether the h-s
 * drawer is open, the live run progress and final result.
 *
 * The canvas itself uses React Flow's own store for nodes / edges; we
 * only keep the *meta* state here.
 */

import { create } from "zustand";
import type { CycleResult } from "@/lib/api/types";

interface RunState {
  jobId?: string;
  status: "idle" | "running" | "succeeded" | "failed";
  progress: number;
  iteration: number;
  residual: number;
  detail?: string;
  result?: CycleResult;
}

interface CycleUiState {
  selectedNodeId?: string;
  hsDrawerOpen: boolean;
  resultPanelOpen: boolean;
  run: RunState;
  /**
   * True while the Properties-Panel form holds un-saved edits.
   *
   * Surfaces two UX guards:
   *  - Run Cycle warns the user that the solver will read the *backend* values,
   *    not their pending edits (the form's dirty buffer isn't flushed until
   *    Save).
   *  - A `beforeunload` listener prevents accidentally closing the tab
   *    / navigating away with un-saved edits.
   */
  hasUnsavedEdits: boolean;

  setSelectedNode(id: string | undefined): void;
  setHsDrawerOpen(open: boolean): void;
  setResultPanelOpen(open: boolean): void;
  setUnsavedEdits(dirty: boolean): void;
  startRun(jobId: string): void;
  pushRunEvent(event: {
    progress: number;
    iteration: number;
    residual: number;
    detail?: string;
  }): void;
  finishRun(status: "succeeded" | "failed", result?: CycleResult): void;
  resetRun(): void;
}

export const useCycleUiStore = create<CycleUiState>((set) => ({
  selectedNodeId: undefined,
  hsDrawerOpen: false,
  resultPanelOpen: false,
  run: { status: "idle", progress: 0, iteration: 0, residual: NaN },
  hasUnsavedEdits: false,

  setSelectedNode(id) {
    set({ selectedNodeId: id });
  },
  setHsDrawerOpen(open) {
    set({ hsDrawerOpen: open });
  },
  setResultPanelOpen(open) {
    set({ resultPanelOpen: open });
  },
  setUnsavedEdits(dirty) {
    set({ hasUnsavedEdits: dirty });
  },
  startRun(jobId) {
    set({
      run: { jobId, status: "running", progress: 0, iteration: 0, residual: NaN },
      resultPanelOpen: false,
    });
  },
  pushRunEvent(event) {
    set((s) => ({
      run: {
        ...s.run,
        status: "running",
        progress: event.progress,
        iteration: event.iteration,
        residual: event.residual,
        detail: event.detail,
      },
    }));
  },
  finishRun(status, result) {
    // Open the result panel on success OR when a structured failure
    // came back — the panel now hosts the friendly-error display, so we
    // need it visible so the user can read what went wrong.
    const hasFailure = !!result?.failure;
    set((s) => ({
      run: { ...s.run, status, result, progress: 1 },
      resultPanelOpen: status === "succeeded" || hasFailure,
      hsDrawerOpen:
        status === "succeeded" && !hasFailure ? true : s.hsDrawerOpen,
    }));
  },
  resetRun() {
    set({
      run: { status: "idle", progress: 0, iteration: 0, residual: NaN },
    });
  },
}));
