/**
 * Candidate detail page state classification (U8).
 *
 * Pure logic, kept free of React so the node-script tests in
 * `src/__tests__/candidate-detail-state.test.mjs` can pin the state map
 * (the .mjs mirror is the runtime guard; this TS source is authoritative).
 *
 * The page is self-sufficient from the URL: it never assumes a warm client
 * store, so every state below must be derivable from fetch outcomes alone.
 */

import type {
  CandidateFetchOutcome,
  ServerCandidate,
} from "@/lib/api/flowpath";

/**
 * - `loading`        — candidate fetch still in flight.
 * - `ok`             — candidate resolved, belongs to this project, from the
 *                      latest exploration job (or recency is unknowable).
 * - `stale`          — resolvable, but from a non-latest exploration job:
 *                      render with the provenance label + warning chip.
 * - `expired`        — 404: unknown id or restart-expired (candidates are
 *                      ephemeral; the index dies with the server). Renders
 *                      the designed not-found / "re-run exploration" state.
 * - `cross-project`  — the candidate exists but belongs to another project:
 *                      presents as not-found (same designed state).
 * - `error`          — network / server error, distinct from not-found.
 */
export type CandidateDetailState =
  | "loading"
  | "ok"
  | "stale"
  | "expired"
  | "cross-project"
  | "error";

export function classifyCandidateDetail(args: {
  /** `null` while the fetch is in flight. */
  outcome: CandidateFetchOutcome | null;
  routeProjectId: string;
  /**
   * Job id of the most recent finished exploration for this project, or
   * `null` when unknowable (no runs visible — e.g. jobs list still loading
   * or empty). Unknowable recency must NOT mark a candidate stale.
   */
  latestExploreJobId: string | null;
}): CandidateDetailState {
  const { outcome, routeProjectId, latestExploreJobId } = args;
  if (outcome === null) return "loading";
  if (outcome.kind === "not-found") return "expired";
  if (outcome.kind === "error") return "error";
  const cand = outcome.candidate;
  // Candidates have carried project_id since the explore worker first wrote
  // them; a missing field means an out-of-date server — treat as foreign.
  if (!cand.project_id || cand.project_id !== routeProjectId) {
    return "cross-project";
  }
  if (latestExploreJobId !== null && cand.job_id !== latestExploreJobId) {
    return "stale";
  }
  return "ok";
}

/** The explore evaluator's REGIME_OUT_OF_VALIDITY sentinel for M_rel. */
const M_REL_SENTINEL = 9.99;

export interface ObjectiveDisplay {
  /** Rendered text — "—" for sentinels, formatted number otherwise. */
  text: string;
  /** True when the value is a sentinel (tooltip explains why). */
  sentinel: boolean;
}

/**
 * Sentinel-aware objective formatting: the `M_rel: 9.99` marker and the
 * zeroed objectives of non-VALID candidates are placeholders the solver
 * wrote *because no real number exists* — they must never render as
 * engineering values.
 */
export function objectiveDisplay(
  key: string,
  value: number | undefined,
  status: string,
  decimals = 4,
): ObjectiveDisplay {
  if (value === undefined || !Number.isFinite(value)) {
    return { text: "—", sentinel: true };
  }
  if (key === "M_rel" && Math.abs(value - M_REL_SENTINEL) < 1e-9) {
    return { text: "—", sentinel: true };
  }
  if (status !== "VALID" && value === 0) {
    return { text: "—", sentinel: true };
  }
  return { text: value.toFixed(decimals), sentinel: false };
}

/** Candidate status → chip presentation (icon + text, never colour alone). */
export interface StatusChip {
  label: string;
  variant: "success" | "warning" | "danger";
  /** lucide icon name, resolved by the page component. */
  icon: "check" | "alert-triangle" | "x-octagon";
}

export function candidateStatusChip(status: string): StatusChip {
  switch (status) {
    case "VALID":
      return { label: "VALID", variant: "success", icon: "check" };
    case "REGIME_OUT_OF_VALIDITY":
      return {
        label: "Regime out of validity",
        variant: "warning",
        icon: "alert-triangle",
      };
    case "NON_CONVERGED":
      return {
        label: "Non-converged",
        variant: "warning",
        icon: "alert-triangle",
      };
    case "INVALID_GEOMETRY":
      return {
        label: "Invalid geometry",
        variant: "danger",
        icon: "x-octagon",
      };
    case "MANUFACTURABILITY_FAILED":
      return {
        label: "Not manufacturable",
        variant: "danger",
        icon: "x-octagon",
      };
    default:
      return { label: status, variant: "warning", icon: "alert-triangle" };
  }
}

/** Reason the handoff actions are disabled, or null when allowed. */
export function handoffDisabledReason(args: {
  candidate: ServerCandidate | null;
  hasCompressor: boolean | null; // null = components still loading
}): string | null {
  const { candidate, hasCompressor } = args;
  if (!candidate) return "Candidate not loaded.";
  if (candidate.status === "MANUFACTURABILITY_FAILED") {
    // The design point solved fine — the geometry just can't be made.
    return (
      "This candidate cannot be produced on a standard 5-axis machining " +
      "cell — an unmakeable geometry cannot honestly drive the cycle " +
      "co-simulation. Loosen the manufacturability overrides and re-run " +
      "the exploration to reconsider it."
    );
  }
  if (candidate.status !== "VALID") {
    return (
      "This candidate's own design point refused " +
      `(${candidate.status}) — its geometry cannot honestly drive the ` +
      "cycle co-simulation."
    );
  }
  if (hasCompressor === false) {
    return (
      "This project's cycle canvas has no Compressor component to " +
      "receive the geometry. Add one on the Cycle page first."
    );
  }
  return null;
}
