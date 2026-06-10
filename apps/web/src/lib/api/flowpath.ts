/**
 * Flow Path PD page API surface.
 *
 * These types and helpers wrap the FastAPI server in `apps/api/` (default
 * `http://localhost:8000`). They are intentionally additive — the rest of
 * the front-end keeps using the mock client in `client.ts`. The Flow Path
 * page is the first surface that talks to the real backend.
 */

const DEFAULT_API_BASE =
  process.env.NEXT_PUBLIC_CASCADE_API_BASE_URL ?? "http://localhost:8000";

export function apiBase(): string {
  return DEFAULT_API_BASE;
}

// ---------------------------------------------------------------------------
// Server candidate / job / loss model shapes (mirrors apps/api/models.py)
// ---------------------------------------------------------------------------

export interface ServerCandidate {
  id: string;
  job_id: string;
  /** Owning project — used by the detail route's cross-project guard. */
  project_id?: string | null;
  index: number;
  params: Record<string, number>;
  objectives: Record<string, number>;
  constraints: Record<string, boolean>;
  status: string;
  error_message?: string | null;
}

export interface ServerJobEvent {
  job_id: string;
  status: string;
  progress: number;
  message: string;
  data?: {
    candidates_batch?: ServerCandidate[];
    n_total?: number;
    n_done?: number;
  };
}

export interface ServerJob {
  id: string;
  project_id: string;
  kind: string;
  status: string;
  progress: number;
  message: string;
  created_at: string;
  updated_at: string;
  finished_at?: string | null;
  error?: string | null;
  result?: Record<string, unknown> | null;
}

export interface ServerLossModel {
  name: string;
  machine_class: string;
  citation: string;
  description: string;
  scale_factors: Record<string, number>;
  validity_envelope: Record<string, number>;
}

// ---------------------------------------------------------------------------
// Request shapes
// ---------------------------------------------------------------------------

export interface ParameterRangeRequest {
  min: number;
  max: number;
  unit: string;
  scale: "linear" | "log";
}

export interface ExploreRequestBody {
  n_samples: number;
  seed: number;
  parallelism: number;
  parameter_ranges: Record<string, ParameterRangeRequest>;
  primary_objective: string;
  minimize_primary: boolean;
}

// ---------------------------------------------------------------------------
// HTTP helpers (REST endpoints — non-SSE)
// ---------------------------------------------------------------------------

export async function postExplore(
  projectId: string,
  body: ExploreRequestBody,
  signal?: AbortSignal,
): Promise<{ job_id: string }> {
  const r = await fetch(
    `${apiBase()}/api/projects/${projectId}/explore`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      signal,
    },
  );
  if (!r.ok) {
    throw new Error(`explore failed: ${r.status} ${r.statusText}`);
  }
  return r.json();
}

export async function cancelJob(jobId: string): Promise<void> {
  await fetch(`${apiBase()}/api/jobs/${jobId}`, { method: "DELETE" }).catch(
    () => undefined,
  );
}

export async function getJob(jobId: string, signal?: AbortSignal): Promise<ServerJob> {
  const r = await fetch(`${apiBase()}/api/jobs/${jobId}`, { signal });
  if (!r.ok) throw new Error(`job ${jobId}: ${r.status}`);
  return r.json();
}

export async function getCandidate(
  candidateId: string,
  signal?: AbortSignal,
): Promise<ServerCandidate> {
  const r = await fetch(`${apiBase()}/api/candidates/${candidateId}`, {
    signal,
  });
  if (!r.ok) throw new Error(`candidate ${candidateId}: ${r.status}`);
  return r.json();
}

// ---------------------------------------------------------------------------
// Candidate detail + geometry handoff (U8)
// ---------------------------------------------------------------------------

/** HTTP error that keeps the status code so callers can branch on 404/422. */
export class FlowPathApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "FlowPathApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function flowPathJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const r = await fetch(`${apiBase()}${path}`, {
    headers: init?.body
      ? { "content-type": "application/json" }
      : undefined,
    ...init,
  });
  if (!r.ok) {
    let detail: unknown;
    try {
      detail = await r.json();
    } catch {
      detail = undefined;
    }
    // FastAPI's error body is {detail: ...} where detail is either a
    // plain string or a structured dict ({error_code, message, ...}).
    // Mirrors fetchJson's extraction in client.ts: string detail passes
    // through, structured detail prefers `message`, any other dict is
    // JSON-stringified — never "[object Object]".
    const d = detail as { detail?: unknown } | undefined;
    let message = `HTTP ${r.status}`;
    if (typeof detail === "string" && detail) {
      message = detail;
    } else if (
      typeof detail === "object" &&
      detail !== null &&
      "detail" in detail
    ) {
      const inner = (detail as { detail: unknown }).detail;
      if (typeof inner === "string") {
        message = inner;
      } else if (
        inner !== null &&
        typeof inner === "object" &&
        typeof (inner as { message?: unknown }).message === "string"
      ) {
        message = (inner as { message: string }).message;
      } else if (inner != null) {
        try {
          message = JSON.stringify(inner);
        } catch {
          /* keep the HTTP fallback */
        }
      }
    }
    throw new FlowPathApiError(r.status, message, d?.detail);
  }
  if (r.status === 204) return undefined as unknown as T;
  return r.json();
}

/** Fetch a candidate, distinguishing 404 (expired/unknown) from other errors. */
export type CandidateFetchOutcome =
  | { kind: "ok"; candidate: ServerCandidate }
  | { kind: "not-found" }
  | { kind: "error"; message: string };

export async function fetchCandidateOutcome(
  candidateId: string,
  signal?: AbortSignal,
): Promise<CandidateFetchOutcome> {
  try {
    const r = await fetch(
      `${apiBase()}/api/candidates/${encodeURIComponent(candidateId)}`,
      { signal },
    );
    if (r.status === 404) return { kind: "not-found" };
    if (!r.ok) return { kind: "error", message: `HTTP ${r.status}` };
    return { kind: "ok", candidate: (await r.json()) as ServerCandidate };
  } catch (err) {
    return {
      kind: "error",
      message: err instanceof Error ? err.message : String(err),
    };
  }
}

/** The full merged geometry a candidate resolves to (the handoff write set). */
export interface MergedGeometry {
  candidate_id: string;
  machine_class: string;
  geometry_params: Record<string, number>;
  operating_point: Record<string, number | string>;
  sampled_keys: string[];
  meanline_rpm_rpm: number;
  /** Meridional (z, r) polylines in metres — {"hub": [[z,r],...],
   *  "shroud": [[z,r],...]}; empty when the server lacks cascade.geometry. */
  meridional: Record<string, [number, number][]>;
}

export async function getMergedGeometry(
  candidateId: string,
  projectId: string,
  signal?: AbortSignal,
): Promise<MergedGeometry> {
  return flowPathJson<MergedGeometry>(
    `/api/candidates/${encodeURIComponent(candidateId)}/merged-geometry?project_id=${encodeURIComponent(projectId)}`,
    { signal },
  );
}

export interface SendToCycleResult {
  project_id: string;
  candidate_id: string;
  component_id: string;
  geometry_params: Record<string, number>;
  meanline_rpm_rpm: number;
  aligned: boolean;
  pressure_ratio: number | null;
  mass_flow_kg_per_s: number | null;
}

export async function sendCandidateToCycle(
  candidateId: string,
  projectId: string,
  alignOperatingPoint: boolean,
): Promise<SendToCycleResult> {
  return flowPathJson<SendToCycleResult>(
    `/api/candidates/${encodeURIComponent(candidateId)}/send-to-cycle`,
    {
      method: "POST",
      body: JSON.stringify({
        project_id: projectId,
        align_operating_point: alignOperatingPoint,
      }),
    },
  );
}

export interface PinCandidateResult {
  project_id: string;
  active_candidate_id: string;
  snapshot: Record<string, unknown>;
}

export async function pinCandidate(
  candidateId: string,
  projectId: string,
): Promise<PinCandidateResult> {
  return flowPathJson<PinCandidateResult>(
    `/api/candidates/${encodeURIComponent(candidateId)}/pin`,
    {
      method: "POST",
      body: JSON.stringify({ project_id: projectId }),
    },
  );
}

export async function detachComponentGeometry(
  projectId: string,
  componentId: string,
): Promise<void> {
  await flowPathJson<void>(
    `/api/projects/${encodeURIComponent(projectId)}/components/${encodeURIComponent(componentId)}/geometry`,
    { method: "DELETE" },
  );
}

/** Raw (untranslated) components — exposes geometry_params, which the
 * cycle-page param translation deliberately does not surface. */
export interface RawComponent {
  id: string;
  kind: string;
  name: string;
  params: Record<string, unknown>;
}

export async function getRawComponents(
  projectId: string,
  signal?: AbortSignal,
): Promise<RawComponent[]> {
  const body = await flowPathJson<{ components: RawComponent[] }>(
    `/api/projects/${encodeURIComponent(projectId)}/components`,
    { signal },
  );
  return body.components;
}

/** Project settings bag (active_candidate_id, pinned_candidates, …). */
export async function getProjectSettings(
  projectId: string,
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  const detail = await flowPathJson<{
    settings?: Record<string, unknown>;
  }>(`/api/projects/${encodeURIComponent(projectId)}`, { signal });
  return detail.settings ?? {};
}

export function geometryUrl(
  candidateId: string,
  lod: "preview" | "standard" | "high" = "standard",
): string {
  return `${apiBase()}/api/candidates/${candidateId}/geometry?lod=${lod}`;
}

export type DownloadFormat = "glb" | "stl" | "step" | "iges" | "fluid.step" | "turbogrid.ndf";

export function downloadUrl(
  candidateId: string,
  format: DownloadFormat,
): string {
  return `${apiBase()}/api/candidates/${candidateId}/export.${format}`;
}

/**
 * Probe whether the server has the optional `cascade[cad]` extra installed,
 * i.e. whether STEP / IGES exports are available. Falls back to `false` on
 * any network or parse error so the UI never claims availability that
 * isn't there.
 *
 * Called once on page load by the Flow Path PD page (ADAPT-033).
 */
export async function cadExportAvailable(signal?: AbortSignal): Promise<boolean> {
  try {
    const r = await fetch(`${apiBase()}/api/candidates/_cad/available`, { signal });
    if (!r.ok) return false;
    const body = (await r.json()) as { available?: boolean };
    return Boolean(body.available);
  } catch {
    return false;
  }
}

/**
 * W-19: Probe the dedicated ``GET /api/health/cad`` endpoint that returns
 * both availability and the installed OCCT version string.
 *
 * Falls back to ``{ cad_available: false, occt_version: null }`` on any
 * network or parse error — the UI should treat any falsy ``cad_available``
 * as unavailable.
 */
export interface CadHealthResponse {
  cad_available: boolean;
  occt_version: string | null;
}

export async function cadHealth(signal?: AbortSignal): Promise<CadHealthResponse> {
  try {
    const r = await fetch(`${apiBase()}/api/health/cad`, { signal });
    if (!r.ok) return { cad_available: false, occt_version: null };
    return (await r.json()) as CadHealthResponse;
  } catch {
    return { cad_available: false, occt_version: null };
  }
}

export async function listLossModels(
  signal?: AbortSignal,
): Promise<ServerLossModel[]> {
  try {
    const r = await fetch(`${apiBase()}/api/loss-models`, { signal });
    if (!r.ok) throw new Error(`loss-models: ${r.status}`);
    return r.json();
  } catch {
    // Server unreachable — return the canonical fallback so the picker stays
    // useful for design review. These mirror what the API returns when the
    // cascade package is importable.
    return FALLBACK_LOSS_MODELS;
  }
}

// ---------------------------------------------------------------------------
// Fallback data (used when the FastAPI server is offline so the UI still
// reads well during front-end-only review).
// ---------------------------------------------------------------------------

export const FALLBACK_LOSS_MODELS: ServerLossModel[] = [
  {
    name: "whitfield-baines-radial-v1",
    machine_class: "radial_turbine",
    citation:
      "Whitfield, A. and Baines, N.C. (1990). Design of Radial Turbomachines. Longman Scientific & Technical.",
    description:
      "Mean-line loss model for radial-inflow turbines. Includes incidence, passage friction, tip-clearance, disc-friction, and exit-kinetic-energy losses.",
    scale_factors: {
      incidence: 1.0,
      passage: 1.0,
      tip_clearance: 1.0,
      disc_friction: 1.0,
      exit_kinetic_energy: 1.0,
    },
    validity_envelope: {
      M_rel_max: 1.2,
      Re_min: 5e4,
      tip_clearance_ratio_max: 0.05,
    },
  },
  {
    name: "aungier-centrifugal-v1",
    machine_class: "centrifugal_compressor",
    citation:
      "Aungier, R.H. (2000). Centrifugal Compressors: A Strategy for Aerodynamic Design and Analysis. ASME Press.",
    description:
      "Mean-line loss model for centrifugal compressors. Covers inducer incidence, blade-loading, skin-friction, mixing, disc-friction, recirculation, and leakage losses.",
    scale_factors: {
      incidence: 1.0,
      blade_loading: 1.0,
      skin_friction: 1.0,
      mixing: 1.0,
      disc_friction: 1.0,
      recirculation: 1.0,
      leakage: 1.0,
    },
    validity_envelope: {
      M_rel_max: 1.4,
      Re_min: 1e5,
      tip_clearance_ratio_max: 0.07,
    },
  },
  {
    name: "stanitz-slip",
    machine_class: "slip_factor",
    citation: "Stanitz, J.D. (1952). NACA TN 2610.",
    description:
      "Stanitz slip-factor correlation. Independent of blade-count for radial-tipped impellers.",
    scale_factors: {},
    validity_envelope: {},
  },
  {
    name: "wiesner-slip",
    machine_class: "slip_factor",
    citation:
      "Wiesner, F.J. (1967). 'A review of slip factors for centrifugal impellers.' ASME J. Eng. Power.",
    description:
      "Wiesner slip-factor correlation. Most common for backswept centrifugal impellers.",
    scale_factors: {},
    validity_envelope: {},
  },
  {
    name: "stodola-slip",
    machine_class: "slip_factor",
    citation: "Stodola, A. (1927). Steam and Gas Turbines. McGraw-Hill.",
    description:
      "Stodola slip-factor correlation. Original blade-count / outlet-blade-angle form.",
    scale_factors: {},
    validity_envelope: {},
  },
];
