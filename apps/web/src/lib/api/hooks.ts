"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getApiClient } from "./client";
import type { ManufacturabilityReport } from "./types";

const api = getApiClient();

export const queryKeys = {
  projects: ["projects"] as const,
  project: (id: string) => ["project", id] as const,
  cycle: (id: string) => ["project", id, "cycle"] as const,
  candidates: (id: string) => ["project", id, "candidates"] as const,
  map: (id: string) => ["project", id, "map"] as const,
  rotor: (id: string) => ["project", id, "rotor"] as const,
  runs: (id: string) => ["project", id, "runs"] as const,
  manufacturability: (id: string) =>
    ["project", id, "manufacturability"] as const,
};

export function useProjects() {
  return useQuery({
    queryKey: queryKeys.projects,
    queryFn: () => api.listProjects(),
  });
}

export function useProject(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.project(id ?? ""),
    queryFn: () => api.getProject(id!),
    enabled: Boolean(id),
  });
}

/**
 * Display name for a project that is *stable across SSR + first client
 * render*. The naive `project?.name ?? id` causes a hydration mismatch:
 * the server renders the slug (TanStack Query cache is empty) and the
 * client renders the human name (cache rehydrates synchronously). React
 * complains "server rendered text didn't match the client".
 *
 * This hook always returns the slug on the first render (server + client),
 * then swaps to the human name in an effect after mount.
 */
export function useProjectDisplayName(id: string): string {
  const { data: project } = useProject(id);
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);
  if (!mounted) return id;
  return project?.name ?? id;
}

export function useCycle(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.cycle(projectId ?? ""),
    queryFn: () => api.getCycle(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useCandidates(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.candidates(projectId ?? ""),
    queryFn: () => api.listCandidates(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useMap(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.map(projectId ?? ""),
    queryFn: () => api.getMap(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useRotorShape(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.rotor(projectId ?? ""),
    queryFn: () => api.getRotorShape(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useRuns(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.runs(projectId ?? ""),
    queryFn: () => api.listRuns(projectId!),
    enabled: Boolean(projectId),
  });
}

/**
 * Manufacturability check report for the active candidate (ADAPT-032).
 *
 * The backend re-runs the check on every GET, so we don't aggressively cache —
 * the report is cheap and the user expects it to reflect any new candidate
 * the explorer just delivered.
 */
export function useManufacturability(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.manufacturability(projectId ?? ""),
    queryFn: () => api.getManufacturability(projectId!),
    enabled: Boolean(projectId),
    staleTime: 0,
  });
}

/**
 * Persist a per-project manufacturability override map and refresh the report.
 */
export function useSetManufacturabilityOverrides(
  projectId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation<
    ManufacturabilityReport,
    Error,
    Record<string, number>
  >({
    mutationFn: (overrides) =>
      api.setManufacturabilityOverrides(projectId!, overrides),
    onSuccess: (report) => {
      if (!projectId) return;
      queryClient.setQueryData(
        queryKeys.manufacturability(projectId),
        report,
      );
    },
  });
}
