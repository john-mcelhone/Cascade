/**
 * Cascade API client.
 *
 * The real client talks to the FastAPI backend at NEXT_PUBLIC_API_URL
 * (default http://localhost:8000). For surfaces the backend doesn't yet
 * expose (per-project demo cycle graphs, headline sparklines, the legacy
 * runs list) we fall back to the deterministic seed data in `mock-data`
 * so existing pages keep rendering. Every fetch uses `credentials: include`
 * so when auth cookies land they ride along automatically.
 */

import {
  CANDIDATES,
  CYCLES,
  MAPS,
  PROJECTS as MOCK_PROJECTS,
  ROTOR_SHAPES,
  RUNS,
} from "./mock-data";
import type {
  ActiveLossModelResponse,
  AnalysisRequestPayload,
  ApiClient,
  Candidate,
  CycleComponentCreate,
  CycleComponentPatch,
  CycleEdge,
  CycleGraph,
  CycleNode,
  CycleResult,
  HealthResponse,
  JobAcceptedResponse,
  JobModel,
  JobProgressEvent,
  LossModelInfo,
  ManufacturabilityReport,
  MapPoint,
  MapRequestPayload,
  MapResult,
  MapResultBackend,
  MaterialRecord,
  PluginLossModelInfo,
  PluginUploadResponse,
  Project,
  ProjectStatus,
  RotorRequestPayload,
  RotorShape,
  RunRecord,
  ValidationCase,
  WorkingFluid,
} from "./types";

/** Tiny artificial latency so loading states are reachable in the UI. */
const NETWORK_DELAY_MS = 60;

function delay<T>(value: T, ms = NETWORK_DELAY_MS): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

function nextId(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 8)}`;
}

/* ---------------------------------------------------------------------------
 * Cycle defaults (used by the mock fallback CRUD)
 * ------------------------------------------------------------------------- */

function defaultChipsFor(kind: CycleNode["kind"]): CycleNode["chips"] {
  switch (kind) {
    case "compressor":
      return [
        { symbol: "PR", value: "3.0" },
        { symbol: "η", value: "0.80" },
      ];
    case "turbine":
      return [
        { symbol: "PR", value: "3.0" },
        { symbol: "η", value: "0.85" },
      ];
    case "burner":
      return [
        { symbol: "T₃", value: "1100 K" },
        { symbol: "ΔP", value: "3.0 %" },
      ];
    case "recuperator":
      return [{ symbol: "ε", value: "0.85" }];
    case "intercooler":
      return [
        { symbol: "ΔT", value: "60 K" },
        { symbol: "ΔP", value: "2.0 %" },
      ];
    case "mixer":
      return [{ symbol: "n", value: "2 in" }];
    case "splitter":
      return [{ symbol: "frac", value: "0.5" }];
    case "duct":
      return [{ symbol: "ΔP", value: "1.0 %" }];
    case "inlet":
      return [
        { symbol: "Pt", value: "101.3 kPa" },
        { symbol: "Tt", value: "288 K" },
      ];
    case "shaft":
      return [
        { symbol: "ω", value: "60 krpm" },
        { symbol: "η_m", value: "0.98" },
      ];
    case "outlet":
      return [];
  }
}

function defaultParamsFor(
  kind: CycleNode["kind"],
): Record<string, number | string | boolean> {
  // Defaults below mirror the Python dataclasses in
  // `src/cascade/cycle/components.py`. Fields beyond the originals (geometry
  // type, bleed, cooling-flow, mechanical-eta) are standard
  // engineering knobs surfaced by the expanded properties panel.
  switch (kind) {
    case "compressor":
      return {
        // essentials
        pressure_ratio: 3.0,
        efficiency_isentropic: 0.8,
        efficiency_mode: "isentropic",
        geometry_type: "centrifugal",
        // advanced
        mechanical_efficiency: 0.99,
        shaft_id: 1,
        bleed_fraction_customer: 0.0,
        bleed_fraction_cooling: 0.0,
      };
    case "turbine":
      return {
        pressure_ratio: 3.0,
        efficiency_isentropic: 0.85,
        efficiency_mode: "isentropic",
        geometry_type: "radial",
        mechanical_efficiency: 0.99,
        shaft_id: 1,
        cooling_flow_fraction: 0.0,
      };
    case "burner":
      return {
        // essentials
        outlet_temperature_K: 1100,
        pressure_drop_fraction: 0.03,
        combustion_efficiency: 0.99,
        spec_mode: "outlet_temperature",
        fuel_species: "CH4",
        // advanced
        fuel_lhv_MJ_per_kg: 50.0,
        fuel_mass_flow_kg_s: 0.0,
      };
    case "recuperator":
      return {
        effectiveness: 0.85,
        cold_pressure_drop_fraction: 0.03,
        hot_pressure_drop_fraction: 0.03,
        heat_transfer_area_m2: 0.0,
      };
    case "intercooler":
      return {
        temperature_drop_K: 60,
        pressure_drop_fraction: 0.02,
        coolant_temperature_K: 300,
        effectiveness: 0.9,
      };
    case "mixer":
      return { n_inputs: 2, pressure_drop_fraction: 0.0 };
    case "splitter":
      return { split_fraction: 0.5, pressure_drop_fraction: 0.0 };
    case "duct":
      return { pressure_drop_fraction: 0.01 };
    case "inlet":
      return {
        pressure_total_kPa: 101.3,
        temperature_total_K: 288,
        mass_flow_kg_s: 0.22,
        pressure_loss_fraction: 0.0,
      };
    case "shaft":
      return { speed_krpm: 60, mechanical_efficiency: 0.98 };
    case "outlet":
      return { pressure_loss_fraction: 0.0 };
  }
}

function defaultResultFor(graph: CycleGraph | undefined): CycleResult {
  if (graph?.result) return graph.result;
  return {
    thermalEfficiency: 0.28,
    electricalEfficiency: 0.265,
    specificWork: 135,
    fuelFlow: 0.0078,
    netShaftWork: 29.5,
    electricalOutput: 27.8,
    components: [],
    states: [],
  };
}

function rebuildChips(
  kind: CycleNode["kind"],
  params: Record<string, number | string | boolean> | undefined,
): CycleNode["chips"] {
  if (!params) return defaultChipsFor(kind);
  const num = (k: string, fallback?: number) =>
    typeof params[k] === "number" ? (params[k] as number) : fallback;
  switch (kind) {
    case "compressor":
    case "turbine":
      return [
        { symbol: "PR", value: fmt(num("pressure_ratio")) },
        { symbol: "η", value: fmt(num("efficiency_isentropic")) },
      ];
    case "burner": {
      // U7: in fuel-mass-flow mode the TIT is a solver OUTPUT — rendering
      // the stored outlet_temperature_K would show a stale number the
      // solver no longer honours. Emit a `derived` chip instead; the
      // canvas (BaseNode) fills its value in from the latest solve and
      // greys it while stale.
      const fuelMode = params.spec_mode === "fuel_mass_flow";
      return [
        fuelMode
          ? { symbol: "T₃", value: "—", derived: true }
          : { symbol: "T₃", value: `${fmt(num("outlet_temperature_K"))} K` },
        {
          symbol: "ΔP",
          value: `${fmt((num("pressure_drop_fraction") ?? 0) * 100, 1)} %`,
        },
      ];
    }
    case "recuperator":
      return [
        { symbol: "ε", value: fmt(num("effectiveness")) },
        {
          symbol: "ΔP_c",
          value: `${fmt(
            (num("cold_pressure_drop_fraction") ?? 0) * 100,
            1,
          )} %`,
        },
      ];
    case "intercooler":
      return [
        { symbol: "ΔT", value: `${fmt(num("temperature_drop_K"))} K` },
        {
          symbol: "ΔP",
          value: `${fmt((num("pressure_drop_fraction") ?? 0) * 100, 1)} %`,
        },
      ];
    case "inlet":
      return [
        { symbol: "Pt", value: `${fmt(num("pressure_total_kPa"))} kPa` },
        { symbol: "Tt", value: `${fmt(num("temperature_total_K"))} K` },
      ];
    case "shaft":
      return [
        { symbol: "ω", value: `${fmt(num("speed_krpm"))} krpm` },
        { symbol: "η_m", value: fmt(num("mechanical_efficiency")) },
      ];
    case "duct":
      return [
        {
          symbol: "ΔP",
          value: `${fmt((num("pressure_drop_fraction") ?? 0) * 100, 1)} %`,
        },
      ];
    case "splitter":
      return [{ symbol: "frac", value: fmt(num("split_fraction")) }];
    case "mixer":
      return [{ symbol: "n", value: `${num("n_inputs") ?? 2} in` }];
    case "outlet":
      return [];
  }
}

function fmt(v: number | undefined, decimals = 2): string {
  if (v === undefined || !Number.isFinite(v)) return "—";
  return v.toFixed(decimals).replace(/\.?0+$/, "");
}

/* ---------------------------------------------------------------------------
 * Real backend HTTP plumbing
 * ------------------------------------------------------------------------- */

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function getApiBaseUrl(): string {
  if (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, "");
  }
  return "http://localhost:8000";
}

async function fetchJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const base = getApiBaseUrl();
  const url = path.startsWith("http") ? path : `${base}${path}`;
  const headers = new Headers(init?.headers ?? {});
  // FormData bodies must let the browser set the Content-Type +
  // multipart boundary. Everything else defaults to JSON.
  const isFormData =
    typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (init?.body && !headers.has("Content-Type") && !isFormData) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("Accept", "application/json");
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers,
      credentials: "include",
    });
  } catch (err) {
    throw new ApiError(
      0,
      `Network error reaching ${url}: ${(err as Error).message}`,
    );
  }
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    // FastAPI's error body is {detail: ...} where detail is either a
    // plain string or a structured dict ({error_code, message, ...} —
    // e.g. the 422 air-standard + live-meanline conflict). Stringifying
    // the dict directly rendered "[object Object]" in toasts; prefer the
    // structured `message` field.
    let msg = `HTTP ${res.status}`;
    if (typeof detail === "string" && detail) {
      msg = detail;
    } else if (typeof detail === "object" && detail !== null && "detail" in detail) {
      const inner = (detail as { detail: unknown }).detail;
      if (typeof inner === "string") {
        msg = inner;
      } else if (
        inner !== null &&
        typeof inner === "object" &&
        typeof (inner as { message?: unknown }).message === "string"
      ) {
        msg = (inner as { message: string }).message;
      } else if (inner != null) {
        try {
          msg = JSON.stringify(inner);
        } catch {
          /* keep the HTTP fallback */
        }
      }
    }
    throw new ApiError(res.status, msg, detail);
  }
  if (res.status === 204) return undefined as unknown as T;
  const text = await res.text();
  if (!text) return undefined as unknown as T;
  return JSON.parse(text) as T;
}

/* ---------------------------------------------------------------------------
 * Adapters from backend shapes to legacy UI shapes
 * ------------------------------------------------------------------------- */

interface BackendProjectSummary {
  id: string;
  name: string;
  kind: string;
  working_fluid: string;
  description: string;
  created_at: string;
  updated_at: string;
  last_run_status?: string | null;
}

interface BackendQuantity {
  value: number;
  unit: string;
}

interface BackendComponent {
  id: string;
  kind: string;
  name: string;
  params: Record<string, unknown>;
  position?: { x: number; y: number };
}

interface BackendEdge {
  id: string;
  source: string;
  target: string;
  source_port?: string;
  target_port?: string;
}

interface BackendComponentsResponse {
  components: BackendComponent[];
  edges: BackendEdge[];
}

interface BackendProjectDetail extends BackendProjectSummary {
  components?: BackendComponent[];
  edges?: BackendEdge[];
  boundary_conditions?: Record<string, unknown>;
  settings?: Record<string, unknown>;
}

/* ---------------------------------------------------------------------------
 * Cycle-graph adapters: backend (Pascal-case kinds + Quantity{value,unit})
 * ↔ UI (lowercase kinds + display-unit plain numbers).
 *
 * The form schemas in `components/cycle/properties-panel.tsx` use display
 * units (kPa for pressures, K for temperatures, MJ/kg for fuel LHV,
 * g/mol for molar mass, %-stored-as-fraction for percentages). The
 * backend stores SI quantities as {value, unit} dicts (or plain numbers
 * for ratios / fractions). These tables bridge the two.
 * ------------------------------------------------------------------------- */

const BACKEND_TO_UI_KIND: Record<string, CycleNode["kind"]> = {
  Inlet: "inlet",
  Outlet: "outlet",
  Compressor: "compressor",
  Turbine: "turbine",
  Burner: "burner",
  Recuperator: "recuperator",
  Intercooler: "intercooler",
  Mixer: "mixer",
  Splitter: "splitter",
  ConstantPressureLoss: "duct",
  Shaft: "shaft",
};

const UI_TO_BACKEND_KIND: Record<CycleNode["kind"], string> = {
  inlet: "Inlet",
  outlet: "Outlet",
  compressor: "Compressor",
  turbine: "Turbine",
  burner: "Burner",
  recuperator: "Recuperator",
  intercooler: "Intercooler",
  mixer: "Mixer",
  splitter: "Splitter",
  duct: "ConstantPressureLoss",
  shaft: "Shaft",
};

function isQuantity(v: unknown): v is BackendQuantity {
  return (
    typeof v === "object" &&
    v !== null &&
    "value" in v &&
    "unit" in v &&
    typeof (v as { value: unknown }).value === "number"
  );
}

/** Convert a backend Quantity {value, unit} to the numeric value in `target` units.
 *
 * Handles the unit conversions we actually use on the Cycle page. Anything
 * else falls back to the raw value (best-effort).
 */
function quantityToUnit(q: BackendQuantity, target: string): number {
  const { value, unit } = q;
  if (unit === target) return value;
  const key = `${unit}->${target}`;
  switch (key) {
    case "Pa->kPa":
      return value / 1000;
    case "kPa->Pa":
      return value * 1000;
    case "Pa->bar":
      return value / 1e5;
    case "kPa->bar":
      return value / 100;
    case "MPa->kPa":
      return value * 1000;
    case "kPa->MPa":
      return value / 1000;
    case "K->K":
      return value;
    case "°C->K":
      return value + 273.15;
    case "K->°C":
      return value - 273.15;
    case "J/kg->MJ/kg":
      return value / 1e6;
    case "MJ/kg->J/kg":
      return value * 1e6;
    case "kg/mol->g/mol":
      return value * 1000;
    case "g/mol->kg/mol":
      return value / 1000;
    case "rpm->krpm":
      return value / 1000;
    case "krpm->rpm":
      return value * 1000;
    case "m**2->m²":
    case "m^2->m²":
      return value;
    default:
      return value; // best-effort
  }
}

/** Helper: pluck a plain number from either a Quantity or a raw number. */
function paramNumber(
  raw: unknown,
  unit?: string,
  fallback = 0,
): number {
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  if (isQuantity(raw)) {
    return unit ? quantityToUnit(raw, unit) : raw.value;
  }
  return fallback;
}

/**
 * Per-kind translation between backend canonical params and the UI form's
 * display-unit params. Each entry in `quantityFields` is
 *   `[backendKey, uiKey, displayUnit]`
 * — when present on the backend as a Quantity, we convert to displayUnit and
 * write `uiKey: number`. When the UI patches `uiKey`, we ship
 * `{ value, unit: displayUnit }` under `backendKey`.
 *
 * `passthroughFields` are keys carried verbatim in both directions (plain
 * numbers, booleans, strings — ratios, fractions, selects, integers).
 * `dropFields` are backend-only keys we don't surface (composition, etc.).
 */
interface KindTranslation {
  quantityFields: Array<[string, string, string]>;
  passthroughFields: string[];
  dropFields: string[];
}

const KIND_TRANSLATIONS: Record<string, KindTranslation> = {
  Inlet: {
    quantityFields: [
      ["pressure_total", "pressure_total_kPa", "kPa"],
      ["temperature_total", "temperature_total_K", "K"],
      ["mass_flow", "mass_flow_kg_s", "kg/s"],
    ],
    passthroughFields: ["pressure_loss_fraction"],
    dropFields: ["composition"],
  },
  Outlet: {
    quantityFields: [],
    passthroughFields: ["pressure_loss_fraction"],
    dropFields: [],
  },
  Compressor: {
    quantityFields: [
      ["mass_flow_override", "mass_flow_override_kg_s", "kg/s"],
      ["inlet_temperature", "inlet_temperature_K", "K"],
    ],
    passthroughFields: [
      "pressure_ratio",
      "efficiency_isentropic",
      "efficiency_mode",
      "geometry_type",
      "mechanical_efficiency",
      "shaft_id",
      "bleed_fraction_customer",
      "bleed_fraction_cooling",
      "material",
    ],
    dropFields: [],
  },
  Turbine: {
    quantityFields: [],
    passthroughFields: [
      "pressure_ratio",
      "efficiency_isentropic",
      "efficiency_mode",
      "geometry_type",
      "mechanical_efficiency",
      "shaft_id",
      "cooling_flow_fraction",
      "material",
    ],
    dropFields: [],
  },
  Burner: {
    quantityFields: [
      ["outlet_temperature", "outlet_temperature_K", "K"],
      ["fuel_lhv", "fuel_lhv_MJ_per_kg", "MJ/kg"],
      ["fuel_molar_mass", "fuel_molar_mass_g_per_mol", "g/mol"],
      ["fuel_mass_flow", "fuel_mass_flow_kg_s", "kg/s"],
    ],
    passthroughFields: [
      "pressure_drop_fraction",
      "combustion_efficiency",
      "spec_mode",
      "fuel_species",
      "fuel_carbon_atoms",
      "fuel_hydrogen_atoms",
      "air_standard",
      "material",
    ],
    dropFields: [],
  },
  Recuperator: {
    quantityFields: [],
    passthroughFields: [
      "effectiveness",
      "cold_pressure_drop_fraction",
      "hot_pressure_drop_fraction",
      "heat_transfer_area_m2",
      "material",
    ],
    dropFields: [],
  },
  Intercooler: {
    quantityFields: [
      ["coolant_temperature", "coolant_temperature_K", "K"],
      ["temperature_drop", "temperature_drop_K", "K"],
    ],
    passthroughFields: [
      "effectiveness",
      "pressure_drop_fraction",
      "material",
    ],
    dropFields: [],
  },
  Mixer: {
    quantityFields: [],
    passthroughFields: ["n_inputs", "pressure_drop_fraction"],
    dropFields: [],
  },
  Splitter: {
    quantityFields: [],
    passthroughFields: ["split_fraction", "pressure_drop_fraction"],
    dropFields: [],
  },
  ConstantPressureLoss: {
    quantityFields: [],
    passthroughFields: ["pressure_drop_fraction"],
    dropFields: [],
  },
  Shaft: {
    quantityFields: [
      ["speed", "speed_krpm", "krpm"],
    ],
    passthroughFields: ["mechanical_efficiency"],
    dropFields: [],
  },
};

/** Backend params (mix of Quantity + plain) → UI params (all plain numbers / strings). */
function backendParamsToUi(
  backendKind: string,
  params: Record<string, unknown> | undefined,
): Record<string, number | string | boolean> {
  const out: Record<string, number | string | boolean> = {};
  if (!params) return out;
  const t = KIND_TRANSLATIONS[backendKind];
  if (!t) {
    // Unknown kind — best-effort: pass plain numbers / strings through;
    // collapse quantities to their value.
    for (const [k, v] of Object.entries(params)) {
      if (typeof v === "number" || typeof v === "string" || typeof v === "boolean") {
        out[k] = v;
      } else if (isQuantity(v)) {
        out[k] = v.value;
      }
    }
    return out;
  }
  for (const [bk, uk, unit] of t.quantityFields) {
    const raw = params[bk];
    if (raw === undefined) continue;
    if (isQuantity(raw)) out[uk] = quantityToUnit(raw, unit);
    else if (typeof raw === "number") out[uk] = raw;
  }
  for (const k of t.passthroughFields) {
    const v = params[k];
    if (v === undefined) continue;
    if (typeof v === "number" || typeof v === "string" || typeof v === "boolean") {
      out[k] = v;
    } else if (isQuantity(v)) {
      // A passthrough field came in as a Quantity (legacy seed) — flatten.
      out[k] = v.value;
    }
  }
  return out;
}

/** UI params (display-unit plain numbers) → backend params (Quantity dicts where needed). */
function uiParamsToBackend(
  backendKind: string,
  params: Record<string, number | string | boolean> | undefined,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (!params) return out;
  const t = KIND_TRANSLATIONS[backendKind];
  if (!t) {
    for (const [k, v] of Object.entries(params)) out[k] = v;
    return out;
  }
  for (const [bk, uk, unit] of t.quantityFields) {
    const raw = params[uk];
    if (raw === undefined) continue;
    if (typeof raw === "number" && Number.isFinite(raw)) {
      out[bk] = { value: raw, unit };
    }
  }
  for (const k of t.passthroughFields) {
    if (params[k] === undefined) continue;
    out[k] = params[k];
  }
  return out;
}

function adaptBackendNode(c: BackendComponent): CycleNode {
  const uiKind: CycleNode["kind"] = BACKEND_TO_UI_KIND[c.kind] ?? "duct";
  const params = backendParamsToUi(c.kind, c.params);
  return {
    id: c.id,
    kind: uiKind,
    label: c.name,
    x: c.position?.x ?? 0,
    y: c.position?.y ?? 0,
    chips: rebuildChips(uiKind, params),
    params,
  };
}

function adaptBackendEdge(e: BackendEdge): CycleEdge {
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    sourcePort: e.source_port,
    targetPort: e.target_port,
  };
}

function adaptStatus(s: string | null | undefined): ProjectStatus {
  switch (s) {
    case "done":
      return "converged";
    case "non_converged":
    case "failed":
      return "diverged";
    case "running":
    case "queued":
      return "in-progress";
    default:
      return "design";
  }
}

function adaptWorkingFluid(s: string): WorkingFluid {
  switch (s) {
    case "co2_supercritical":
      return "co2";
    case "helium":
      return "n2";
    case "custom":
      return "n2";
    case "air":
    default:
      return "air";
  }
}

function adaptTemplate(kind: string): Project["template"] {
  switch (kind) {
    case "microturbine":
      return "microturbine";
    case "sco2":
      return "sco2-loop";
    case "aero":
      return "aero-axial";
    default:
      return "blank";
  }
}

function adaptProjectSummary(s: BackendProjectSummary): Project {
  const seed = MOCK_PROJECTS.find((p) => p.id === s.id);
  return {
    id: s.id,
    name: s.name,
    description: s.description ?? "",
    template: adaptTemplate(s.kind),
    status: adaptStatus(s.last_run_status),
    createdAt: s.created_at,
    updatedAt: s.updated_at,
    workingFluid: adaptWorkingFluid(s.working_fluid),
    headline: seed?.headline ?? { label: "—", value: 0, unit: "" },
    sparkline: seed?.sparkline ?? [],
  };
}

function adaptMapPointStatus(status: string): MapPoint["status"] {
  switch (status) {
    case "CONVERGED":
      return "ok";
    case "STALL_SURGE":
      return "surge";
    case "CHOKED":
      return "choke";
    default:
      return "diverged";
  }
}

export function adaptMapResult(backend: MapResultBackend): MapResult {
  const rpmList = backend.axes.rpm.slice();
  const points: MapPoint[] = backend.points.map((p) => ({
    rpm: p.coords.rpm,
    massFlow: p.coords.m_dot,
    pi_tt: p.outputs.pi,
    eta_tt: p.outputs.eta,
    status: adaptMapPointStatus(p.status),
  }));
  return { rpmList, points };
}

/* ---------------------------------------------------------------------------
 * Runs adaptation (U8): backend JobModel → legacy RunRecord.
 *
 * The runs page renders RunRecord rows; the backend jobs endpoint speaks
 * JobModel. Status mapping: done → succeeded; failed / cancelled / queued /
 * running pass through. Refusals (U1 contract: failed + error null +
 * result.failure) keep the failed badge and gain the `refused` flag so the
 * summary can say "refused" rather than implying a crash. Explore jobs
 * expose `best_id` for the candidate-detail deep link.
 *
 * Mirrored by src/__tests__/candidate-detail-state.test.mjs.
 * ------------------------------------------------------------------------- */

const RUN_KINDS = new Set(["cycle", "explore", "analysis", "map", "rotor"]);

export function adaptJobToRunRecord(job: JobModel): RunRecord {
  const kind = (
    RUN_KINDS.has(job.kind) ? job.kind : "cycle"
  ) as RunRecord["kind"];
  const status: RunRecord["status"] =
    job.status === "done"
      ? "succeeded"
      : job.status === "failed"
        ? "failed"
        : job.status === "cancelled"
          ? "cancelled"
          : job.status === "running"
            ? "running"
            : "queued";
  const startedMs = Date.parse(job.created_at);
  const finishedMs = job.finished_at ? Date.parse(job.finished_at) : NaN;
  const durationMs =
    Number.isFinite(startedMs) && Number.isFinite(finishedMs)
      ? Math.max(0, finishedMs - startedMs)
      : undefined;
  const result = (job.result ?? undefined) as
    | Record<string, unknown>
    | undefined;
  const refused =
    job.status === "failed" &&
    job.error == null &&
    Boolean(result && typeof result === "object" && "failure" in result);
  const bestId =
    kind === "explore" && typeof result?.best_id === "string"
      ? (result.best_id as string)
      : undefined;
  return {
    id: job.id,
    kind,
    status,
    startedAt: job.created_at,
    finishedAt: job.finished_at ?? undefined,
    durationMs,
    summary: job.message || undefined,
    bestCandidateId: bestId,
    refused: refused || undefined,
  };
}

/** Convert a backend cycle-solver `result` dict to our typed CycleResult. */
export function adaptCycleResult(raw: Record<string, unknown>): CycleResult {
  const num = (k: string, fallback = 0): number => {
    const v = raw[k];
    return typeof v === "number" && Number.isFinite(v) ? v : fallback;
  };
  const quantity = (k: string, mul = 1, fallback = 0): number => {
    const v = raw[k];
    if (v && typeof v === "object" && "value" in v) {
      const x = (v as { value: unknown }).value;
      return typeof x === "number" && Number.isFinite(x) ? x * mul : fallback;
    }
    return typeof v === "number" ? v * mul : fallback;
  };
  // Pull the UI-friendly arrays the backend now ships. Both are already
  // in camelCase + display units (K, kPa, kJ/(kg·K), kg/s, kW); we just
  // validate shape.
  const states: CycleResult["states"] = Array.isArray(raw.states)
    ? (raw.states as Array<Record<string, unknown>>).map((s, i) => ({
        label: typeof s.label === "string" ? s.label : String(i + 1),
        temperature: typeof s.temperature === "number" ? s.temperature : 0,
        entropy: typeof s.entropy === "number" ? s.entropy : 0,
        pressure: typeof s.pressure === "number" ? s.pressure : undefined,
        massFlow: typeof s.massFlow === "number" ? s.massFlow : undefined,
      }))
    : [];
  const components: CycleResult["components"] = Array.isArray(raw.components)
    ? (raw.components as Array<Record<string, unknown>>).map((c) => ({
        componentId: typeof c.componentId === "string" ? c.componentId : "?",
        shaftWork: typeof c.shaftWork === "number" ? c.shaftWork : 0,
        outletTemperature:
          typeof c.outletTemperature === "number" ? c.outletTemperature : 0,
        outletPressure:
          typeof c.outletPressure === "number" ? c.outletPressure : 0,
        outletMassFlow:
          typeof c.outletMassFlow === "number" ? c.outletMassFlow : 0,
      }))
    : [];
  // U9: per-rotor efficiency attribution. The backend ships four dicts
  // keyed by component name — converged η, the mode actually used, the
  // mode the user requested (pre-fallback), and an explicit fallback
  // flag. The result panel's "Efficiency sources" block renders from
  // these; dropping them (the pre-U9 behaviour) left a live-meanline
  // fallback invisible. Mirrored by
  // src/__tests__/efficiency-sources.test.mjs.
  const recordOf = <V,>(
    k: string,
    isV: (v: unknown) => v is V,
  ): Record<string, V> | undefined => {
    const v = raw[k];
    if (!v || typeof v !== "object" || Array.isArray(v)) return undefined;
    const out: Record<string, V> = {};
    for (const [name, val] of Object.entries(v as Record<string, unknown>)) {
      if (isV(val)) out[name] = val;
    }
    return out;
  };
  const componentEfficiencies = recordOf(
    "component_efficiencies",
    (v): v is number => typeof v === "number" && Number.isFinite(v),
  );
  const efficiencyModes = recordOf(
    "efficiency_modes",
    (v): v is string => typeof v === "string",
  );
  const requestedEfficiencyModes = recordOf(
    "requested_efficiency_modes",
    (v): v is string => typeof v === "string",
  );
  const efficiencyFallbacks = recordOf(
    "efficiency_fallbacks",
    (v): v is boolean => typeof v === "boolean",
  );
  // Structured-failure envelope (backend `_classify_failure`). Present
  // when the solver couldn't produce a valid answer; the UI surfaces it
  // as a friendly explanation (design issues) or a copy-the-log panel
  // (software bugs).
  let failure: CycleResult["failure"];
  const f = raw.failure;
  if (f && typeof f === "object") {
    const ff = f as Record<string, unknown>;
    const kind = ff.kind === "bug" ? "bug" : "design";
    failure = {
      kind,
      title: typeof ff.title === "string" ? ff.title : "Cycle didn't converge",
      plain_english:
        typeof ff.plain_english === "string"
          ? ff.plain_english
          : "The solver couldn't produce a valid answer for this configuration.",
      suggestions: Array.isArray(ff.suggestions)
        ? (ff.suggestions as unknown[])
            .filter((s): s is string => typeof s === "string")
        : [],
      details: typeof ff.details === "string" ? ff.details : undefined,
      bug_log: typeof ff.bug_log === "string" ? ff.bug_log : undefined,
    };
  }
  return {
    thermalEfficiency: num("thermal_efficiency"),
    electricalEfficiency: num("electrical_efficiency"),
    // Backend specific_work is J/kg in SI; our UI shows kJ/kg.
    specificWork: quantity("specific_work", 1e-3),
    fuelFlow: quantity("fuel_mass_flow"),
    netShaftWork: quantity("net_shaft_work", 1e-3),
    electricalOutput: quantity("electrical_output", 1e-3),
    components,
    states,
    componentEfficiencies,
    efficiencyModes,
    requestedEfficiencyModes,
    efficiencyFallbacks,
    failure,
  };
}

/* ---------------------------------------------------------------------------
 * The real client
 * ------------------------------------------------------------------------- */

class RealApiClient implements ApiClient {
  async health(): Promise<HealthResponse> {
    return fetchJson<HealthResponse>("/api/health");
  }

  async listProjects(): Promise<Project[]> {
    try {
      const backend =
        await fetchJson<BackendProjectSummary[]>("/api/projects");
      return backend.map(adaptProjectSummary);
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) {
        // Backend down — fall back to seed data so the dashboard still renders.
        return delay([...MOCK_PROJECTS]);
      }
      throw err;
    }
  }

  async getProject(id: string): Promise<Project | undefined> {
    try {
      // The detail endpoint also carries `settings`; surface the
      // air-standard flag so the UI can disable fuel-mass-flow mode (U7)
      // without waiting for the backend's synchronous 422.
      const backend = await fetchJson<BackendProjectDetail>(
        `/api/projects/${encodeURIComponent(id)}`,
      );
      const project = adaptProjectSummary(backend);
      project.airStandard = Boolean(backend.settings?.air_standard);
      return project;
    } catch (err) {
      if (
        err instanceof ApiError &&
        (err.status === 404 || err.status === 0)
      ) {
        return MOCK_PROJECTS.find((p) => p.id === id);
      }
      throw err;
    }
  }

  /**
   * Read the cycle graph for a project from the real backend.
   *
   * Maps backend canonical params (Pascal-case kind + Quantity{value,unit})
   * to the UI's display-unit shape used by the properties panel form. Falls
   * back to the mock CYCLES map if the backend is unreachable so the page
   * still renders offline (Storybook / SSR / tests).
   */
  async getCycle(projectId: string): Promise<CycleGraph> {
    try {
      const resp = await fetchJson<BackendComponentsResponse>(
        `/api/projects/${encodeURIComponent(projectId)}/components`,
      );
      return {
        nodes: resp.components.map(adaptBackendNode),
        edges: resp.edges.map(adaptBackendEdge),
      };
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) {
        return delay(CYCLES[projectId] ?? { nodes: [], edges: [] });
      }
      throw err;
    }
  }

  async listCandidates(projectId: string): Promise<Candidate[]> {
    return delay(CANDIDATES[projectId] ?? []);
  }

  async getMap(projectId: string): Promise<MapResult> {
    // Last-completed map results aren't a backend GET yet; surface the seed
    // values for the dashboard preview. The map page itself runs a fresh
    // map on demand via runMap().
    return delay(MAPS[projectId] ?? { rpmList: [], points: [] });
  }

  async getRotorShape(projectId: string): Promise<RotorShape> {
    return delay(ROTOR_SHAPES[projectId] ?? { totalLength: 0, sections: [] });
  }

  /**
   * Real runs history (U8): GET /api/jobs?project_id= adapted to the
   * legacy RunRecord shape. Falls back to the deterministic seed rows only
   * when the backend is unreachable (offline review), never on an empty
   * result — an empty project genuinely has no runs.
   */
  async listRuns(projectId: string): Promise<RunRecord[]> {
    try {
      const jobs = await fetchJson<JobModel[]>(
        `/api/jobs?project_id=${encodeURIComponent(projectId)}`,
      );
      return jobs.map(adaptJobToRunRecord);
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) {
        return delay(RUNS[projectId] ?? []);
      }
      throw err;
    }
  }

  // ---- Cycle CRUD (real backend; falls back to mock CYCLES on network err).
  async addCycleComponent(
    projectId: string,
    payload: CycleComponentCreate,
  ): Promise<CycleNode> {
    const backendKind = UI_TO_BACKEND_KIND[payload.kind] ?? "ConstantPressureLoss";
    const params = payload.params ?? defaultParamsFor(payload.kind);
    const body = {
      kind: backendKind,
      name: payload.label,
      params: uiParamsToBackend(backendKind, params),
      position: { x: payload.x, y: payload.y },
    };
    try {
      const created = await fetchJson<BackendComponent>(
        `/api/projects/${encodeURIComponent(projectId)}/components`,
        { method: "POST", body: JSON.stringify(body) },
      );
      return adaptBackendNode(created);
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) {
        const cycle = CYCLES[projectId] ?? { nodes: [], edges: [] };
        const id = nextId(payload.kind);
        const node: CycleNode = {
          id,
          kind: payload.kind,
          label: payload.label,
          x: payload.x,
          y: payload.y,
          chips: defaultChipsFor(payload.kind),
          params,
        };
        cycle.nodes = [...cycle.nodes, node];
        CYCLES[projectId] = cycle;
        return delay(node, 30);
      }
      throw err;
    }
  }

  async updateCycleComponent(
    projectId: string,
    componentId: string,
    patch: CycleComponentPatch,
  ): Promise<CycleNode> {
    try {
      // We don't know the backend kind without a GET, so the safest path is
      // to first fetch the current component to learn its kind. The
      // components list endpoint is cheap; cache hits make this snappy.
      // Optimisation deferred — current cycles are tiny.
      const resp = await fetchJson<BackendComponentsResponse>(
        `/api/projects/${encodeURIComponent(projectId)}/components`,
      );
      const cur = resp.components.find((c) => c.id === componentId);
      const backendKind = cur?.kind ?? "ConstantPressureLoss";
      const body: Record<string, unknown> = {};
      if (patch.label !== undefined) body.name = patch.label;
      if (patch.params !== undefined) {
        body.params = uiParamsToBackend(backendKind, patch.params);
      }
      if (patch.position !== undefined) body.position = patch.position;
      const updated = await fetchJson<BackendComponent>(
        `/api/projects/${encodeURIComponent(projectId)}/components/${encodeURIComponent(componentId)}`,
        { method: "PATCH", body: JSON.stringify(body) },
      );
      return adaptBackendNode(updated);
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) {
        const cycle = CYCLES[projectId];
        if (!cycle) throw new Error(`Project ${projectId} has no cycle.`);
        const idx = cycle.nodes.findIndex((n) => n.id === componentId);
        if (idx < 0) throw new Error(`Component ${componentId} not found.`);
        const cur = cycle.nodes[idx];
        const next: CycleNode = {
          ...cur,
          label: patch.label ?? cur.label,
          x: patch.position?.x ?? cur.x,
          y: patch.position?.y ?? cur.y,
          params: { ...(cur.params ?? {}), ...(patch.params ?? {}) },
        };
        next.chips = rebuildChips(next.kind, next.params);
        cycle.nodes = [...cycle.nodes];
        cycle.nodes[idx] = next;
        CYCLES[projectId] = cycle;
        return delay(next, 30);
      }
      throw err;
    }
  }

  async deleteCycleComponent(
    projectId: string,
    componentId: string,
  ): Promise<void> {
    try {
      await fetchJson<void>(
        `/api/projects/${encodeURIComponent(projectId)}/components/${encodeURIComponent(componentId)}`,
        { method: "DELETE" },
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) {
        const cycle = CYCLES[projectId];
        if (!cycle) return;
        cycle.nodes = cycle.nodes.filter((n) => n.id !== componentId);
        cycle.edges = cycle.edges.filter(
          (e) => e.source !== componentId && e.target !== componentId,
        );
        CYCLES[projectId] = cycle;
        return delay(undefined, 30);
      }
      throw err;
    }
  }

  async addCycleEdge(
    projectId: string,
    edge: Omit<CycleEdge, "id">,
  ): Promise<CycleEdge> {
    // The backend doesn't yet expose an edge CRUD endpoint; edges live on
    // the project's `edges` array but no PATCH/POST routes are wired up.
    // Until the cycle agent ships that, we mutate the local mock so the
    // canvas reflects user wiring, and emit the change to whatever does
    // hit the wire on next save (no-op today).
    const cycle = CYCLES[projectId] ?? { nodes: [], edges: [] };
    const created: CycleEdge = { id: nextId("e"), ...edge };
    cycle.edges = [...cycle.edges, created];
    CYCLES[projectId] = cycle;
    return delay(created, 30);
  }

  async deleteCycleEdge(projectId: string, edgeId: string): Promise<void> {
    const cycle = CYCLES[projectId];
    if (!cycle) return;
    cycle.edges = cycle.edges.filter((e) => e.id !== edgeId);
    CYCLES[projectId] = cycle;
    return delay(undefined, 30);
  }

  async solveCycle(projectId: string): Promise<{ jobId: string }> {
    try {
      const resp = await fetchJson<JobAcceptedResponse>(
        `/api/projects/${encodeURIComponent(projectId)}/cycle/solve`,
        { method: "POST" },
      );
      return { jobId: resp.job_id };
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) {
        // Backend down — fall back to a synthetic local job so the cycle
        // page's progress UI still has something to render against.
        return { jobId: `cyc-${projectId}-${Date.now().toString(36)}` };
      }
      throw err;
    }
  }

  async saveCycleVersion(
    projectId: string,
    note?: string,
  ): Promise<{ versionId: string }> {
    return delay(
      {
        versionId: `${projectId}-v-${Date.now().toString(36)}${note ? "" : ""}`,
      },
      40,
    );
  }

  async runMap(
    projectId: string,
    payload: MapRequestPayload,
  ): Promise<JobAcceptedResponse> {
    return fetchJson<JobAcceptedResponse>(
      `/api/projects/${encodeURIComponent(projectId)}/map`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  }

  async runRotor(
    projectId: string,
    payload: RotorRequestPayload,
  ): Promise<JobAcceptedResponse> {
    return fetchJson<JobAcceptedResponse>(
      `/api/projects/${encodeURIComponent(projectId)}/rotor`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  }

  async runAnalysis(
    projectId: string,
    payload: AnalysisRequestPayload,
  ): Promise<JobAcceptedResponse> {
    return fetchJson<JobAcceptedResponse>(
      `/api/projects/${encodeURIComponent(projectId)}/analysis`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  }

  async getJob(jobId: string): Promise<JobModel> {
    return fetchJson<JobModel>(`/api/jobs/${encodeURIComponent(jobId)}`);
  }

  async waitForJob(jobId: string, timeoutMs = 60_000): Promise<JobModel> {
    const start = Date.now();
    let interval = 120;
    for (;;) {
      const job = await this.getJob(jobId);
      if (
        job.status === "done" ||
        job.status === "failed" ||
        job.status === "cancelled"
      ) {
        return job;
      }
      if (Date.now() - start > timeoutMs) {
        throw new ApiError(
          0,
          `Job ${jobId} did not finish within ${timeoutMs / 1000}s`,
        );
      }
      await new Promise((r) => setTimeout(r, interval));
      interval = Math.min(interval * 1.7, 500);
    }
  }

  async listLossModels(): Promise<LossModelInfo[]> {
    try {
      return await fetchJson<LossModelInfo[]>("/api/loss-models");
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) return [];
      throw err;
    }
  }

  async listProjectLossModels(
    projectId: string,
    machineClass?: string,
  ): Promise<PluginLossModelInfo[]> {
    const qs = machineClass
      ? `?machine_class=${encodeURIComponent(machineClass)}`
      : "";
    try {
      return await fetchJson<PluginLossModelInfo[]>(
        `/api/projects/${encodeURIComponent(projectId)}/loss-models${qs}`,
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) return [];
      throw err;
    }
  }

  async uploadLossModelPlugin(
    projectId: string,
    file: File,
  ): Promise<PluginUploadResponse> {
    const form = new FormData();
    form.append("file", file);
    return fetchJson<PluginUploadResponse>(
      `/api/projects/${encodeURIComponent(projectId)}/loss-models/upload`,
      { method: "POST", body: form },
    );
  }

  async selectLossModel(
    projectId: string,
    name: string,
  ): Promise<ActiveLossModelResponse> {
    return fetchJson<ActiveLossModelResponse>(
      `/api/projects/${encodeURIComponent(projectId)}/loss-models/${encodeURIComponent(name)}/select`,
      { method: "POST" },
    );
  }

  async deleteLossModelPlugin(
    projectId: string,
    name: string,
  ): Promise<void> {
    await fetchJson<void>(
      `/api/projects/${encodeURIComponent(projectId)}/loss-models/${encodeURIComponent(name)}`,
      { method: "DELETE" },
    );
  }

  async listValidationCases(): Promise<ValidationCase[]> {
    try {
      return await fetchJson<ValidationCase[]>("/api/validation/cases");
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) return [];
      throw err;
    }
  }

  async listMaterials(family?: string): Promise<MaterialRecord[]> {
    const qs = family ? `?family=${encodeURIComponent(family)}` : "";
    try {
      return await fetchJson<MaterialRecord[]>(`/api/materials${qs}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 0)
        return MOCK_MATERIALS_FALLBACK;
      throw err;
    }
  }

  async getMaterial(name: string): Promise<MaterialRecord> {
    return fetchJson<MaterialRecord>(
      `/api/materials/${encodeURIComponent(name)}`,
    );
  }

  async getManufacturability(
    projectId: string,
    candidateId?: string,
  ): Promise<ManufacturabilityReport> {
    const qs = candidateId
      ? `?candidate_id=${encodeURIComponent(candidateId)}`
      : "";
    return fetchJson<ManufacturabilityReport>(
      `/api/projects/${encodeURIComponent(projectId)}/manufacturability${qs}`,
    );
  }

  async setManufacturabilityOverrides(
    projectId: string,
    overrides: Record<string, number>,
  ): Promise<ManufacturabilityReport> {
    return fetchJson<ManufacturabilityReport>(
      `/api/projects/${encodeURIComponent(projectId)}/manufacturability/overrides`,
      { method: "PUT", body: JSON.stringify({ overrides }) },
    );
  }

  /**
   * Stream a job's progress events. If the EventSource API is available
   * (browser context) we wire SSE; on the server we fall back to a
   * polling-style synthetic generator (used by SSR tooling only — pages
   * that stream are all marked "use client").
   */
  async *streamJob(
    jobId: string,
  ): AsyncGenerator<JobProgressEvent, void, void> {
    if (typeof window === "undefined" || typeof EventSource === "undefined") {
      // Server-rendered/test path: poll the job endpoint once and yield the
      // terminal event so consumers don't hang. Detail in the SSE hook.
      const job = await this.getJob(jobId).catch(() => null);
      yield {
        jobId,
        iteration: 1,
        residual: 0,
        progress: 1,
        done: true,
        status:
          job?.status === "failed" || job?.status === "cancelled"
            ? "failed"
            : "succeeded",
        result:
          inferProjectIdFromJobId(jobId) !== undefined
            ? defaultResultFor(CYCLES[inferProjectIdFromJobId(jobId)!])
            : undefined,
      };
      return;
    }

    const base = getApiBaseUrl();
    const url = `${base}/api/jobs/${encodeURIComponent(jobId)}/events`;

    const queue: JobProgressEvent[] = [];
    let waiter: ((ev: JobProgressEvent | undefined) => void) | null = null;
    let closed = false;
    let iteration = 0;

    function push(ev: JobProgressEvent) {
      if (waiter) {
        const w = waiter;
        waiter = null;
        w(ev);
      } else {
        queue.push(ev);
      }
    }

    function finish() {
      closed = true;
      if (waiter) {
        const w = waiter;
        waiter = null;
        w(undefined);
      }
    }

    const es = new EventSource(url, { withCredentials: true });
    es.addEventListener("message", (raw: MessageEvent<string>) => {
      try {
        const data = JSON.parse(raw.data) as {
          progress?: number;
          message?: string;
          status?: string;
          final?: boolean;
          error?: string;
          result?: Record<string, unknown>;
        };
        iteration += 1;
        const ev: JobProgressEvent = {
          jobId,
          iteration,
          residual: 0,
          progress: typeof data.progress === "number" ? data.progress : 0,
          detail: data.message,
        };
        if (data.final) {
          ev.done = true;
          ev.status =
            data.status === "failed" || data.status === "cancelled"
              ? "failed"
              : "succeeded";
          if (data.result) {
            ev.result = adaptCycleResult(data.result);
          }
        }
        push(ev);
        if (data.final) {
          es.close();
          finish();
        }
      } catch {
        // ignore unparseable
      }
    });

    es.addEventListener("error", () => {
      // Native EventSource will retry. We only finish on a final message.
      // If the source is hard-closed (CLOSED state), surface a terminal event.
      if (es.readyState === EventSource.CLOSED) {
        if (!closed) {
          push({
            jobId,
            iteration: iteration + 1,
            residual: 0,
            progress: 1,
            done: true,
            status: "failed",
            detail: "SSE connection closed.",
          });
          finish();
        }
      }
    });

    try {
      while (true) {
        if (queue.length) {
          yield queue.shift()!;
          continue;
        }
        if (closed) break;
        const ev = await new Promise<JobProgressEvent | undefined>(
          (resolve) => {
            waiter = resolve;
          },
        );
        if (ev === undefined) break;
        yield ev;
      }
    } finally {
      es.close();
    }
  }
}

/* ---------------------------------------------------------------------------
 * Mock materials fallback. Used when the API is unreachable (SSR /
 * offline mode) and by MockApiClient. Mirrors the canonical 10 records
 * from cascade.materials.database; values are *truncated* to the room-
 * temperature point so callers still get a sensible picker list, but
 * heavy property tables come from the live API.
 * ------------------------------------------------------------------------- */

const MOCK_MATERIALS_FALLBACK: MaterialRecord[] = [
  ["Inconel 625", "UNS N06625", "Ni-based superalloy", 8440, 0.305],
  ["Inconel 718", "UNS N07718", "Ni-based superalloy", 8190, 0.294],
  ["Inconel 738", "IN-738LC", "Ni-based superalloy", 8110, 0.300],
  ["MAR-M 247", "MAR-M 247", "Ni-based superalloy", 8540, 0.295],
  ["Ti-6Al-4V", "UNS R56400 / Grade 5", "Ti alloy", 4430, 0.342],
  ["AISI 4340", "UNS G43400", "Alloy steel", 7850, 0.290],
  ["17-4PH", "UNS S17400", "Precipitation-hardening stainless", 7800, 0.272],
  ["A286", "UNS S66286", "Fe-Ni-Cr superalloy", 7920, 0.310],
  ["Haynes 282", "UNS N07208", "Ni-based superalloy", 8270, 0.310],
  ["316L", "UNS S31603", "Stainless steel", 8000, 0.270],
].map(([name, designation, family, rho, nu]) => ({
  name: name as string,
  designation: designation as string,
  family: family as string,
  density_kg_per_m3: rho as number,
  poisson: nu as number,
  youngs_modulus_GPa: [[293, 200] as [number, number]],
  yield_strength_MPa: [[293, 0] as [number, number]],
  ultimate_strength_MPa: [[293, 0] as [number, number]],
  thermal_expansion_1_per_K: [[293, 12e-6] as [number, number]],
  thermal_conductivity_W_per_mK: [[293, 15] as [number, number]],
  specific_heat_J_per_kgK: [[293, 500] as [number, number]],
  source: "offline-fallback",
  notes: "Mock fallback — connect to the API for full property tables.",
}));

/* ---------------------------------------------------------------------------
 * Mock client (kept around so unit tests / Storybook can opt in)
 * ------------------------------------------------------------------------- */

class MockApiClient implements ApiClient {
  async health(): Promise<HealthResponse> {
    return delay({
      status: "ok",
      version: "0.1.0",
      cascade_version: "0.1.0",
      service: "cascade-web-mock",
    });
  }

  async listProjects(): Promise<Project[]> {
    return delay([...MOCK_PROJECTS]);
  }

  async getProject(id: string): Promise<Project | undefined> {
    return delay(MOCK_PROJECTS.find((p) => p.id === id));
  }

  async getCycle(projectId: string): Promise<CycleGraph> {
    return delay(CYCLES[projectId] ?? { nodes: [], edges: [] });
  }

  async listCandidates(projectId: string): Promise<Candidate[]> {
    return delay(CANDIDATES[projectId] ?? []);
  }

  async getMap(projectId: string): Promise<MapResult> {
    return delay(MAPS[projectId] ?? { rpmList: [], points: [] });
  }

  async getRotorShape(projectId: string): Promise<RotorShape> {
    return delay(ROTOR_SHAPES[projectId] ?? { totalLength: 0, sections: [] });
  }

  async listRuns(projectId: string): Promise<RunRecord[]> {
    return delay(RUNS[projectId] ?? []);
  }

  async addCycleComponent(
    projectId: string,
    payload: CycleComponentCreate,
  ): Promise<CycleNode> {
    const cycle = CYCLES[projectId] ?? { nodes: [], edges: [] };
    const id = nextId(payload.kind);
    const node: CycleNode = {
      id,
      kind: payload.kind,
      label: payload.label,
      x: payload.x,
      y: payload.y,
      chips: defaultChipsFor(payload.kind),
      params: payload.params ?? defaultParamsFor(payload.kind),
    };
    cycle.nodes = [...cycle.nodes, node];
    CYCLES[projectId] = cycle;
    return delay(node, 30);
  }

  async updateCycleComponent(
    projectId: string,
    componentId: string,
    patch: CycleComponentPatch,
  ): Promise<CycleNode> {
    const cycle = CYCLES[projectId];
    if (!cycle) throw new Error(`Project ${projectId} has no cycle.`);
    const idx = cycle.nodes.findIndex((n) => n.id === componentId);
    if (idx < 0) throw new Error(`Component ${componentId} not found.`);
    const cur = cycle.nodes[idx];
    const next: CycleNode = {
      ...cur,
      label: patch.label ?? cur.label,
      x: patch.position?.x ?? cur.x,
      y: patch.position?.y ?? cur.y,
      params: { ...(cur.params ?? {}), ...(patch.params ?? {}) },
    };
    next.chips = rebuildChips(next.kind, next.params);
    cycle.nodes = [...cycle.nodes];
    cycle.nodes[idx] = next;
    CYCLES[projectId] = cycle;
    return delay(next, 30);
  }

  async deleteCycleComponent(
    projectId: string,
    componentId: string,
  ): Promise<void> {
    const cycle = CYCLES[projectId];
    if (!cycle) return;
    cycle.nodes = cycle.nodes.filter((n) => n.id !== componentId);
    cycle.edges = cycle.edges.filter(
      (e) => e.source !== componentId && e.target !== componentId,
    );
    CYCLES[projectId] = cycle;
    return delay(undefined, 30);
  }

  async addCycleEdge(
    projectId: string,
    edge: Omit<CycleEdge, "id">,
  ): Promise<CycleEdge> {
    const cycle = CYCLES[projectId] ?? { nodes: [], edges: [] };
    const created: CycleEdge = { id: nextId("e"), ...edge };
    cycle.edges = [...cycle.edges, created];
    CYCLES[projectId] = cycle;
    return delay(created, 30);
  }

  async deleteCycleEdge(projectId: string, edgeId: string): Promise<void> {
    const cycle = CYCLES[projectId];
    if (!cycle) return;
    cycle.edges = cycle.edges.filter((e) => e.id !== edgeId);
    CYCLES[projectId] = cycle;
    return delay(undefined, 30);
  }

  async solveCycle(projectId: string): Promise<{ jobId: string }> {
    return delay({ jobId: `cyc-${projectId}-${Date.now().toString(36)}` }, 30);
  }

  async saveCycleVersion(
    projectId: string,
    note?: string,
  ): Promise<{ versionId: string }> {
    return delay(
      {
        versionId: `${projectId}-v-${Date.now().toString(36)}${note ? "" : ""}`,
      },
      40,
    );
  }

  async runMap(
    projectId: string,
    _payload: MapRequestPayload,
  ): Promise<JobAcceptedResponse> {
    void _payload;
    return delay({ job_id: `map-${projectId}-${Date.now().toString(36)}` }, 30);
  }

  async runRotor(
    projectId: string,
    _payload: RotorRequestPayload,
  ): Promise<JobAcceptedResponse> {
    void _payload;
    return delay({ job_id: `rot-${projectId}-${Date.now().toString(36)}` }, 30);
  }

  async runAnalysis(
    projectId: string,
    _payload: AnalysisRequestPayload,
  ): Promise<JobAcceptedResponse> {
    void _payload;
    return delay({ job_id: `ana-${projectId}-${Date.now().toString(36)}` }, 30);
  }

  async getJob(jobId: string): Promise<JobModel> {
    return delay({
      id: jobId,
      project_id: "unknown",
      kind: "cycle",
      status: "done",
      progress: 1,
      message: "Mock job complete.",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
      error: null,
      result: null,
    });
  }

  async waitForJob(jobId: string): Promise<JobModel> {
    return this.getJob(jobId);
  }

  async listLossModels(): Promise<LossModelInfo[]> {
    return delay([]);
  }

  async listProjectLossModels(
    _projectId: string,
    _machineClass?: string,
  ): Promise<PluginLossModelInfo[]> {
    return delay([
      {
        name: "WhitfieldBainesRadial",
        origin: "builtin",
        applicable_machine_classes: ["radial_turbine"],
        description: "Mock built-in.",
        citation: "Whitfield & Baines 1990.",
        author: "Cascade",
        version: "1.0",
      },
      {
        name: "AungierCentrifugal",
        origin: "builtin",
        applicable_machine_classes: ["centrifugal_compressor"],
        description: "Mock built-in.",
        citation: "Aungier 2000.",
        author: "Cascade",
        version: "1.0",
      },
    ]);
  }

  async uploadLossModelPlugin(
    _projectId: string,
    file: File,
  ): Promise<PluginUploadResponse> {
    return delay({
      plugin: {
        name: file.name.replace(/\.py$/, ""),
        origin: "user",
        applicable_machine_classes: ["radial_turbine"],
        description: "(mock upload)",
        citation: "",
        author: "",
        version: "0.1.0",
      },
      stored_path: `/mock/${file.name}`,
      message: "Mock upload accepted.",
    });
  }

  async selectLossModel(
    projectId: string,
    name: string,
  ): Promise<ActiveLossModelResponse> {
    return delay({ project_id: projectId, active_loss_model: name });
  }

  async deleteLossModelPlugin(
    _projectId: string,
    _name: string,
  ): Promise<void> {
    return delay(undefined);
  }

  async listValidationCases(): Promise<ValidationCase[]> {
    return delay([]);
  }

  async listMaterials(family?: string): Promise<MaterialRecord[]> {
    const all = MOCK_MATERIALS_FALLBACK;
    return delay(
      family
        ? all.filter((m) => m.family.toLowerCase() === family.toLowerCase())
        : all,
    );
  }

  async getMaterial(name: string): Promise<MaterialRecord> {
    const m = MOCK_MATERIALS_FALLBACK.find((x) => x.name === name);
    if (!m) throw new ApiError(404, `Unknown material ${name}`);
    return delay(m);
  }

  async getManufacturability(
    _projectId: string,
    _candidateId?: string,
  ): Promise<ManufacturabilityReport> {
    void _projectId;
    void _candidateId;
    // Mock: return an all-pass report so the UI panel can hydrate offline.
    return delay({
      machine_class: "centrifugal_compressor",
      geometry_name: "mock-impeller",
      checked_at: new Date().toISOString(),
      violations: [],
      passes: [
        {
          rule_name: "le_thickness_min",
          description: "Leading-edge thickness at inlet.",
          measured: 0.45e-3,
          threshold_min: 0.30e-3,
          threshold_max: null,
          units: "m",
          citation: "AMRC 5-axis cutter survey 2019",
        },
      ],
      overrides_used: {},
      has_violations: false,
      critical_count: 0,
      warning_count: 0,
      rule_count: 1,
      geometry: { impeller_outlet_radius_m: 0.1, blade_count: 20 },
      candidate_id: null,
    });
  }

  async setManufacturabilityOverrides(
    projectId: string,
    _overrides: Record<string, number>,
  ): Promise<ManufacturabilityReport> {
    void _overrides;
    return this.getManufacturability(projectId);
  }

  async *streamJob(
    jobId: string,
  ): AsyncGenerator<JobProgressEvent, void, void> {
    const totalIterations = 24;
    let residual = 1;
    const projectId = inferProjectIdFromJobId(jobId);
    const graph = projectId ? CYCLES[projectId] : undefined;
    for (let i = 1; i <= totalIterations; i++) {
      residual *= 0.65 + 0.1 * Math.sin(i * 0.7);
      await new Promise((r) => setTimeout(r, 80));
      yield {
        jobId,
        iteration: i,
        residual: Math.max(residual, 1e-9),
        progress: i / totalIterations,
        detail: `iter ${i} / ${totalIterations}`,
      };
    }
    yield {
      jobId,
      iteration: totalIterations,
      residual,
      progress: 1,
      done: true,
      status: "succeeded",
      result: defaultResultFor(graph),
    };
  }
}

function inferProjectIdFromJobId(jobId: string): string | undefined {
  if (!jobId.startsWith("cyc-")) return undefined;
  const rest = jobId.slice("cyc-".length);
  const dash = rest.lastIndexOf("-");
  return dash > 0 ? rest.slice(0, dash) : undefined;
}

let _client: ApiClient | null = null;

/** Singleton accessor for the API client. */
export function getApiClient(): ApiClient {
  if (!_client) _client = new RealApiClient();
  return _client;
}

/** For tests / Storybook: swap in the in-memory mock. */
export function getMockApiClient(): ApiClient {
  return new MockApiClient();
}
